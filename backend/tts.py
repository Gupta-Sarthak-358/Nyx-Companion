import asyncio
from collections.abc import AsyncIterator
import struct
import os
import re
import subprocess
import tempfile
import shlex
import time
from contextlib import suppress
from typing import Any

from fastapi import WebSocket

from config import PIPER_BINARY, PIPER_MODEL
from log_utils import logger


def _run_piper(text: str) -> bytes:
    if not text or not text.strip():
        return b""
    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name
        subprocess.run(
            [PIPER_BINARY, "--model", PIPER_MODEL, "--output-file", tmp_name],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        with open(tmp_name, "rb") as f:
            data = f.read()
        return data
    except subprocess.TimeoutExpired:
        logger.warning("Piper timed out for text: %.50s", text)
        return b""
    except Exception:
        logger.exception("Piper TTS failed")
        return b""
    finally:
        if tmp_name:
            with suppress(OSError):
                os.unlink(tmp_name)

# Patterns whose periods should NOT trigger a sentence break
_ABBREVIATIONS: re.Pattern = re.compile(
    r"\b(?:"
    r"Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|vs|etc|approx|dept|vol|no|Rs"
    r"|Esq|Hon|Rev|Capt|Lt|Cmdr|Sgt|al|fig|inc|ltd|co|corp"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|e\.g|i\.e|a\.m|p\.m"
    r")\.(?:\s+[A-Z]\.)?"
)
_NO_SPLIT: re.Pattern = re.compile(
    _ABBREVIATIONS.pattern + r"|\d+\.\d+\.\d+|\d+\.\d+|[vV]\d+\.\d+|[A-Z]\.(?=\s+[A-Z])"
)


def split_sentences(text: str) -> list[str]:
    protected: set[int] = set()
    for m in _NO_SPLIT.finditer(text):
        for pos in range(m.start(), m.end()):
            if text[pos] == ".":
                protected.add(pos)

    sentences: list[str] = []
    current: list[str] = []
    chars: list[str] = list(text)

    for i, ch in enumerate(chars):
        current.append(ch)
        if ch in ".!?" and i not in protected:
            next_is_end: bool = i + 1 >= len(chars)
            j: int = i + 1
            while j < len(chars) and chars[j] in " \t\n\r":
                j += 1
            next_is_cap: bool = j < len(chars) and chars[j].isupper()
            next_is_quote: bool = j < len(chars) and chars[j] in "\"'"
            if next_is_end or next_is_cap or next_is_quote or ch in "!?":
                sentences.append("".join(current).strip())
                current = []

    remaining: str = "".join(current).strip()
    if remaining:
        sentences.append(remaining)

    return sentences if sentences else [text]


def _build_audio_frame(audio_bytes: bytes, seq: int = 0) -> bytes:
    return struct.pack("<BI", 0x01, seq) + audio_bytes


async def generate_tts(text: str, websocket: WebSocket) -> None:
    audio_bytes: bytes = await asyncio.get_event_loop().run_in_executor(None, _run_piper, text)
    if audio_bytes:
        await websocket.send_bytes(_build_audio_frame(audio_bytes, seq=0))


async def stream_tts_tokens(
    token_generator: AsyncIterator[str],
    websocket: WebSocket,
) -> AsyncIterator[str]:
    buffer: str = ""
    seq: int = 0
    pending_chunks: list[tuple[int, asyncio.Task[bytes]]] = []

    async for token in token_generator:
        buffer += token
        yield token

        sentences: list[str] = split_sentences(buffer)
        if len(sentences) > 1:
            for s in sentences[:-1]:
                seq += 1
                t = asyncio.get_event_loop().run_in_executor(None, _run_piper, s)
                pending_chunks.append((seq, t))
            buffer = sentences[-1]

    if buffer.strip():
        seq += 1
        t = asyncio.get_event_loop().run_in_executor(None, _run_piper, buffer)
        pending_chunks.append((seq, t))

    if not pending_chunks:
        return

    for chunk_seq, task in pending_chunks:
        audio_bytes: bytes = await task
        if audio_bytes:
            await websocket.send_bytes(_build_audio_frame(audio_bytes, seq=chunk_seq))

    await websocket.send_json({"type": "audio_done"})
