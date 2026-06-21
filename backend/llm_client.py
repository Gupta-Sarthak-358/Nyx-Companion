import asyncio
from collections.abc import AsyncIterator
import json
import time
from typing import Any

import httpx

from config import LLAMA_URL

MAX_RETRIES: int = 3
BASE_DELAY: float = 1.0


async def _request_with_retry(method: str, url: str, **kwargs: Any) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 90)) as client:
                response: httpx.Response = await client.request(method, url, **kwargs)
                if response.status_code >= 500 and attempt < MAX_RETRIES:
                    delay: float = BASE_DELAY * (2 ** attempt)
                    from log_utils import logger
                    logger.warning("LLM %d retry after HTTP %d in %.1fs", attempt + 1, response.status_code, delay)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                delay: float = BASE_DELAY * (2 ** attempt)
                from log_utils import logger
                logger.warning("LLM %d retry after %s in %.1fs", attempt + 1, type(e).__name__, delay)
                await asyncio.sleep(delay)
                continue
            raise
    raise last_exc


def build_payload(
    prompt: str,
    stop_tokens: list[str],
    temperature: float,
    top_k: int | None,
    repeat_penalty: float | None,
    stream: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": prompt,
        "n_predict": 250,
        "temperature": temperature,
        "stop": stop_tokens,
    }
    if stream:
        payload["stream"] = True
    if top_k is not None:
        payload["top_k"] = top_k
    if repeat_penalty is not None:
        payload["repeat_penalty"] = repeat_penalty
    return payload


async def _stream_request(
    url: str,
    **kwargs: Any,
) -> AsyncIterator[str]:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 90)) as client:
                async with client.stream("POST", url, **kwargs) as response:
                    if response.status_code >= 500 and attempt < MAX_RETRIES:
                        delay: float = BASE_DELAY * (2 ** attempt)
                        from log_utils import logger
                        logger.warning("LLM stream %d retry after HTTP %d in %.1fs", attempt + 1, response.status_code, delay)
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        yield line
                    return
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                delay: float = BASE_DELAY * (2 ** attempt)
                from log_utils import logger
                logger.warning("LLM stream %d retry after %s in %.1fs", attempt + 1, type(e).__name__, delay)
                await asyncio.sleep(delay)
                continue
            raise
    raise last_exc


async def ask_llm_stream(
    prompt: str,
    stop_tokens: list[str] | None = None,
    temperature: float = 0.7,
    top_k: int | None = None,
    repeat_penalty: float | None = None,
) -> AsyncIterator[str]:
    if stop_tokens is None:
        stop_tokens = ["Candidate:", "User:", "\n[", "\n("]
    payload = build_payload(prompt, stop_tokens, temperature, top_k, repeat_penalty, stream=True)
    try:
        async for line in _stream_request(LLAMA_URL, json=payload, timeout=90):
            if line.startswith("data: "):
                data: dict[str, Any] = json.loads(line[6:])
                yield data.get("content", "")
                if data.get("stop"):
                    break
    except Exception:
        from log_utils import logger
        logger.exception("LLM streaming failed after %d retries", MAX_RETRIES)


async def ask_llm(
    prompt: str,
    stop_tokens: list[str] | None = None,
    task_name: str = "Dialogue",
    temperature: float = 0.7,
    top_k: int | None = None,
    repeat_penalty: float | None = None,
) -> str:
    if stop_tokens is None:
        stop_tokens = ["Candidate:", "User:", "\n[", "\n("]
    from log_utils import logger
    logger.info("LLM request: %s", task_name)
    start_t: float = time.time()
    payload = build_payload(prompt, stop_tokens, temperature, top_k, repeat_penalty)
    try:
        response = await _request_with_retry("POST", LLAMA_URL, json=payload, timeout=90)
        res_text: str = response.json()["content"].strip()
        logger.info("LLM %s finished in %.2fs", task_name, time.time() - start_t)
        return res_text
    except Exception:
        logger.exception("LLM %s failed after %d retries", task_name, MAX_RETRIES)
        return ""


async def check_llama_health() -> bool:
    health_url = LLAMA_URL.replace("/completion", "/health")
    try:
        response = await _request_with_retry("GET", health_url, timeout=5)
        return response.json().get("status") == "ok"
    except Exception as e:
        from log_utils import logger
        logger.warning("llama-server health check failed")
        return False
