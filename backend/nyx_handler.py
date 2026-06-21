import asyncio
import random

from fastapi import WebSocket

from llm_client import ask_llm_stream
from nyx_personality import (
    apply_anti_repetition,
    build_prompt,
    choose_tone,
    clean_response,
    trim_turns,
)
from tts import stream_tts_tokens
from log_utils import logger
import prompt_loader

RAG_SYSTEM_PROMPT = prompt_loader.get("nyx_rag", "system")

NYX_GENERATION_OPTIONS = {"temperature": 0.85, "top_k": 40, "repeat_penalty": 1.2}


async def handle_nyx_message(
    websocket: WebSocket,
    user_text: str,
    history_turns: list,
    last_tone: str | None,
    tts_enabled: bool,
    rag_enabled: bool,
    rag_context_log: list,
    user_role: str = "User",
    ai_role: str = "Nyx",
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[str, str]:
    rag_context = ""
    if rag_enabled:
        try:
            from rag.retriever import retrieve, format_context
            from rag.compressor import compress_results, compress_context_text

            results = retrieve(user_text, top_k=5)
            results = compress_results(results)
            rag_context = format_context(results)
            rag_context = compress_context_text(rag_context)
            if rag_context:
                history_str = ""
                if rag_context_log:
                    entries = "\n".join(
                        f"Previous Q: {h['q']} [sources: {', '.join(h.get('sources', []))}]"
                        for h in rag_context_log[-4:]
                    )
                    history_str = f"--- CONVERSATION HISTORY ---\n{entries}\n\n"
                rag_context = (
                    f"{RAG_SYSTEM_PROMPT}\n\n"
                    f"{history_str}"
                    f"--- KNOWLEDGE BASE CONTEXT ---\n"
                    f"{rag_context}\n"
                    f"--- END CONTEXT ---\n"
                )
                rag_context_log.append(
                    {"q": user_text, "sources": [m.get("source", "") for _, m, _ in results]}
                )
        except Exception:
            logger.exception("Nyx RAG retrieval failed")

    tone = choose_tone(last_tone)

    prompt = build_prompt(
        history_turns, user_text, tone, user_role=user_role, ai_role=ai_role, rag_context=rag_context
    )

    async def _generate():
        token_gen = ask_llm_stream(
            prompt,
            stop_tokens=[f"{user_role}:", f"{ai_role}:", "###"],
            **NYX_GENERATION_OPTIONS,
        )
        if tts_enabled:
            full_res = ""
            async for token in stream_tts_tokens(token_gen, websocket):
                full_res += token
                await websocket.send_json({"type": "ai_token", "token": token})
                await asyncio.sleep(0.01)
        else:
            full_res = ""
            async for token in token_gen:
                full_res += token
                await websocket.send_json({"type": "ai_token", "token": token})
                await asyncio.sleep(0.01)
        return full_res

    if semaphore:
        async with semaphore:
            full_res = await _generate()
    else:
        full_res = await _generate()

    full_res = clean_response(full_res, user_role, ai_role)
    if not full_res:
        await websocket.send_json({"type": "status", "message": "Sorry, I couldn't generate a response. Please try again."})
        return "", tone

    adjusted_res = apply_anti_repetition(full_res, history_turns)
    if adjusted_res != full_res:
        await websocket.send_json({"type": "ai_token", "token": adjusted_res[len(full_res):]})
        full_res = adjusted_res

    await websocket.send_json({"type": "ai_response", "text": full_res})

    history_turns.extend([f"{user_role}: {user_text}", f"{ai_role}: {full_res}"])
    history_turns[:] = trim_turns(history_turns)

    return full_res, tone
