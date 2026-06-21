import json
import os
import time
import base64
import tempfile
import asyncio
from asyncio import Semaphore
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from faster_whisper import WhisperModel
import uvicorn

from config import FRONTEND_DIST, WHISPER_MODEL_SIZE, PIPER_BINARY
from llm_client import check_llama_health
from nyx_handler import handle_nyx_message
from nyx_personality import choose_tone

from mode_handlers import (
    init_mode,
    handle_interview_chat,
    handle_interview_audio,
    handle_retry,
    handle_nudge,
    handle_end_interview,
    handle_mcq_message,
)
from mode_utils import rebuild_history
from session_store import session_store, pack_session, unpack_session
from tts import generate_tts
from log_utils import logger

# ---------------------------------------------------------------------------
# RAG imports (top-level, not lazy)
# ---------------------------------------------------------------------------
try:
    from rag.integration import build_rag_prompt
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("RAG module not available — Tutor mode disabled")

# ---------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Preload models at startup
# ---------------------------------------------------------------------------
logger.info("Loading Whisper model (%s)...", WHISPER_MODEL_SIZE)
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, compute_type="int8")
logger.info("Whisper ready")

# Preload embedding & reranker models so first RAG query is snappy
if RAG_AVAILABLE:
    try:
        from rag.embeddings import get_embedding_model
        from rag.reranker import get_reranker
        logger.info("Preloading embedding model ...")
        get_embedding_model()
        logger.info("Embedding model ready")
        logger.info("Preloading cross-encoder reranker ...")
        get_reranker()
        logger.info("Reranker ready")
    except Exception:
        logger.warning("Could not preload RAG models", exc_info=True)

import prompt_loader
prompt_loader.load_all()
SYSTEM_PROMPT_TEMPLATE = prompt_loader.get("interview", "system")

# ---------------------------------------------------------------------------
# Ingest progress tracker (thread-safe for background ingest)
# ---------------------------------------------------------------------------
_ingest_progress = {"running": False, "current": 0, "total": 0, "file": "", "status": ""}


def _update_ingest_progress(source=None, step=0, total_steps=0, status="", current_file=0, total_files=0):
    _ingest_progress.update({
        "running": True,
        "file": source or _ingest_progress.get("file", ""),
        "step": step,
        "total_steps": total_steps,
        "status": status,
        "current_file": current_file or _ingest_progress.get("current_file", 0),
        "total_files": total_files or _ingest_progress.get("total_files", 0),
    })


# ---------------------------------------------------------------------------
# WebSocket: Interview (also handles Tutor, Conversation, Nyx as mode)
# ---------------------------------------------------------------------------
@app.websocket("/ws/interview")
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")

    _session_id = None
    state = {
        "ws": websocket,
        "whisper_model": whisper_model,
        "rag_available": RAG_AVAILABLE,
        "system_prompt": "",
        "conversation_history": "",
        "history_turns": [],
        "user_role": "User",
        "ai_role": "AI",
        "current_mode": "STRUCTURED",
        "is_scenario_setup_needed": False,
        "session_evals": [],
        "session_acoustic_hits": {"filler_total": 0, "turn_count": 0, "wpm_values": []},
        "rag_context_log": [],
        "nyx_last_tone": None,
        "nyx_tts_enabled": False,
        "nyx_rag_enabled": False,
        "nyx_rag_context_log": [],
    }

    if not await check_llama_health():
        logger.error("llama-server not responding at startup")
        await websocket.send_json({"type": "status", "message": "LLM server is not responding. Please restart."})
        return

    def _save():
        if _session_id:
            session_store.save(_session_id, pack_session(
                history_turns=state["history_turns"],
                session_evals=state["session_evals"],
                rag_context_log=state["rag_context_log"],
                current_mode=state["current_mode"],
                conversation_history=state["conversation_history"],
                system_prompt=state["system_prompt"],
                user_role=state["user_role"],
                ai_role=state["ai_role"],
                is_scenario_setup_needed=state["is_scenario_setup_needed"],
                nyx_last_tone=state["nyx_last_tone"],
                nyx_tts_enabled=state["nyx_tts_enabled"],
                nyx_rag_enabled=state["nyx_rag_enabled"],
                nyx_rag_context_log=state["nyx_rag_context_log"],
                session_acoustic_hits=state["session_acoustic_hits"],
            ))

    try:
        while True:
            raw = await websocket.receive_json()
            from ws_models import parse_ws_message
            validated = parse_ws_message(json.dumps(raw), websocket)
            if validated is None:
                continue
            data = raw
            msg_type = validated.type
            state["data"] = data

            if msg_type == "start":
                _session_id = data.get("session_id")
                mode = data.get("mode", "STRUCTURED").upper()
                custom_desc = data.get("description", "").strip()
                logger.info("Starting session in %s mode", mode)

                if _session_id and (saved := session_store.get(_session_id)):
                    restored = unpack_session(saved, {
                        "history_turns": [], "session_evals": [],
                        "rag_context_log": [], "conversation_history": "",
                        "system_prompt": "", "user_role": "User", "ai_role": "AI",
                        "is_scenario_setup_needed": False, "nyx_last_tone": None,
                        "nyx_tts_enabled": False, "nyx_rag_enabled": False,
                        "nyx_rag_context_log": [],
                        "session_acoustic_hits": {"filler_total": 0, "turn_count": 0, "wpm_values": []},
                        "mcq_subject": None, "mcq_topic": None,
                    })
                    state.update(restored)
                    state["_llm_semaphore"] = Semaphore(1)
                    state["_last_msg_time"] = 0.0
                    logger.info("Restored session %s (%d turns)", _session_id, len(state["history_turns"]))
                    await websocket.send_json({"type": "session_restored", "turns": state["history_turns"], "mode": state["current_mode"]})
                    continue

                if mode == "MCQ":
                    state["current_mode"] = "MCQ"
                    state["history_turns"] = []
                    state["session_evals"] = []
                    state["rag_context_log"] = []
                    state["user_role"] = "User"
                    state["ai_role"] = "Tutor"
                    state["_llm_semaphore"] = Semaphore(1)
                    state["_last_msg_time"] = 0.0
                    state["system_prompt"] = "MCQ Practice Mode"
                    opening = "MCQ practice initialized."
                    state["history_turns"].append(f"{state['ai_role']}: {opening}")
                    state["conversation_history"] = rebuild_history(
                        state["current_mode"], state["history_turns"], state["system_prompt"]
                    )
                    _save()
                    continue

                if mode == "NYX":
                    state["current_mode"] = "NYX"
                    state["history_turns"] = []
                    state["session_evals"] = []
                    state["rag_context_log"] = []
                    state["nyx_last_tone"] = choose_tone()
                    state["nyx_tts_enabled"] = bool(data.get("tts_enabled", False))
                    state["nyx_rag_enabled"] = bool(data.get("rag_enabled", False))
                    state["nyx_rag_context_log"] = []
                    state["user_role"] = "User"
                    state["ai_role"] = "Nyx"
                    state["_llm_semaphore"] = Semaphore(1)
                    state["_last_msg_time"] = 0.0
                    state["system_prompt"] = "You are Nyx, a personal assistant."
                    if custom_desc:
                        state["system_prompt"] += f"\n\nCONTEXT: {custom_desc}"
                    opening = "You again."
                else:
                    await init_mode(data, state, SYSTEM_PROMPT_TEMPLATE, RAG_AVAILABLE)
                    _save()
                    continue

                state["history_turns"].append(f"{state['ai_role']}: {opening}")
                state["conversation_history"] = rebuild_history(
                    state["current_mode"], state["history_turns"], state["system_prompt"]
                )
                await websocket.send_json({"type": "ai_response", "text": opening})
                if state["nyx_tts_enabled"]:
                    await generate_tts(opening, websocket)
                _save()
                continue

            now = time.time()
            if now - state.get("_last_msg_time", 0) < 0.2:
                continue
            state["_last_msg_time"] = now

            if msg_type == "chat_message":
                if state["current_mode"] == "NYX":
                    _, state["nyx_last_tone"] = await handle_nyx_message(
                        websocket, data.get("text", "").strip(), state["history_turns"],
                        state["nyx_last_tone"], state["nyx_tts_enabled"], state["nyx_rag_enabled"],
                        state["nyx_rag_context_log"], user_role=state["user_role"],
                        ai_role=state["ai_role"], semaphore=state["_llm_semaphore"],
                    )
                else:
                    await handle_interview_chat(state)

                _save()
                continue

            elif msg_type == "toggle_tts":
                state["nyx_tts_enabled"] = bool(data.get("enabled", False))
                logger.info("Nyx TTS toggled to %s", state["nyx_tts_enabled"])
                continue

            elif msg_type == "toggle_rag":
                state["nyx_rag_enabled"] = bool(data.get("enabled", False))
                logger.info("Nyx RAG toggled to %s", state["nyx_rag_enabled"])
                continue

            elif msg_type == "audio":
                if state["current_mode"] == "NYX":
                    audio_b64 = data.get("data", "")
                    audio_bytes = base64.b64decode(audio_b64)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    try:
                        tmp.write(audio_bytes)
                        tmp.flush()
                        segments, _ = whisper_model.transcribe(tmp.name, beam_size=1)
                        user_text = " ".join(seg.text for seg in segments).strip()
                    except Exception:
                        logger.exception("Audio transcription failed")
                        user_text = ""
                    finally:
                        tmp.close()
                        with suppress(OSError):
                            os.unlink(tmp.name)

                    if user_text:
                        await websocket.send_json({"type": "user_speech", "text": user_text, "feedback": None})
                else:
                    await handle_interview_audio(state)

                _save()
                continue

            elif msg_type in ("mcq_start", "mcq_answer", "mcq_next", "mcq_end"):
                state["current_mode"] = "MCQ"
                await handle_mcq_message(state)
                _save()
                continue

            elif msg_type == "retry":
                if state["current_mode"] != "NYX":
                    await handle_retry(state)
                _save()
                continue

            elif msg_type == "nudge":
                if state["current_mode"] != "NYX":
                    await handle_nudge(state)
                _save()
                continue

            elif msg_type == "end_interview":
                await handle_end_interview(state)
                continue

    except WebSocketDisconnect:
        _save()
        logger.info("WebSocket disconnected")
    except (asyncio.CancelledError, KeyboardInterrupt):
        _save()
        raise
    except Exception:
        _save()
        logger.exception("WebSocket loop error")

# ---------------------------------------------------------------------------
# Knowledge Management API
# ---------------------------------------------------------------------------

@app.get("/api/knowledge/stats")
async def knowledge_stats():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.vector_store import count_documents, list_sources
        return {"chunks": count_documents(), "sources": list_sources()}
    except Exception as e:
        logger.exception("Failed to get knowledge stats")
        return {"error": str(e)}


@app.get("/api/knowledge/sources")
async def knowledge_sources():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.vector_store import list_sources
        from rag.vector_store import get_collection
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        sources = {}
        for m in (results.get("metadatas") or []):
            s = m.get("source", "unknown")
            if s not in sources:
                sources[s] = {"chunks": 0, "pages": set()}
            sources[s]["chunks"] += 1
            if m.get("page"):
                sources[s]["pages"].add(m["page"])
        for s in sources:
            sources[s]["pages"] = sorted(sources[s]["pages"])
        return {"sources": sources}
    except Exception as e:
        logger.exception("Failed to list sources")
        return {"error": str(e)}


@app.delete("/api/knowledge/sources/{source}")
async def knowledge_delete(source: str):
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.vector_store import delete_source
        deleted = delete_source(source)
        return {"deleted": deleted}
    except Exception as e:
        logger.exception("Failed to delete source")
        return {"error": str(e)}


@app.post("/api/knowledge/ingest")
async def knowledge_ingest():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.ingest import ingest_all
        import asyncio
        _ingest_progress["running"] = True
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ingest_all, _update_ingest_progress)
        _ingest_progress["running"] = False
        return {"status": "done"}
    except Exception as e:
        _ingest_progress["running"] = False
        logger.exception("Failed to ingest")
        return {"error": str(e)}


@app.get("/api/knowledge/ingest-progress")
async def knowledge_ingest_progress():
    return {**_ingest_progress}


MAX_UPLOAD_BYTES = 100 * 1024 * 1024

@app.post("/api/knowledge/upload")
async def knowledge_upload(file: UploadFile = File(...)):
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are accepted"}
    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            return {"error": f"File exceeds 100 MB limit ({len(content) / 1024 / 1024:.1f} MB)"}
        from config import BOOKS_DIR
        os.makedirs(BOOKS_DIR, exist_ok=True)
        dest = os.path.join(BOOKS_DIR, file.filename)
        with open(dest, "wb") as f:
            f.write(content)
        logger.info("Uploaded PDF: %s (%d bytes)", file.filename, len(content))
        return {"status": "uploaded", "filename": file.filename}
    except Exception as e:
        logger.exception("Failed to upload PDF")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
@app.get("/api/diagnostics")
async def api_diagnostics():
    checks = {}

    # LLM
    try:
        from llm_client import check_llama_health
        checks["llm"] = {"ok": await check_llama_health()}
    except Exception as e:
        checks["llm"] = {"ok": False, "error": str(e)}

    # Whisper
    checks["whisper"] = {"ok": whisper_model is not None}

    # Piper
    checks["piper"] = {"ok": os.path.isfile(PIPER_BINARY)}

    # Embedding model
    if RAG_AVAILABLE:
        try:
            from rag.embeddings import get_embedding_model
            checks["embedding"] = {"ok": get_embedding_model() is not None}
        except Exception as e:
            checks["embedding"] = {"ok": False, "error": str(e)}
        try:
            from rag.reranker import get_reranker
            checks["reranker"] = {"ok": get_reranker() is not None}
        except Exception as e:
            checks["reranker"] = {"ok": False, "error": str(e)}
        try:
            from rag.vector_store import get_client
            get_client()
            checks["chroma"] = {"ok": True}
        except Exception as e:
            checks["chroma"] = {"ok": False, "error": str(e)}
    else:
        checks["embedding"] = {"ok": False, "reason": "RAG not available"}
        checks["reranker"] = {"ok": False, "reason": "RAG not available"}
        checks["chroma"] = {"ok": False, "reason": "RAG not available"}

    # Sessions
    from session_store import session_store
    checks["sessions"] = {"count": session_store.active_count}

    # Metrics snapshot
    from metrics import snapshot
    checks["metrics"] = snapshot()

    all_ok = all(v.get("ok", True) or "reason" in v for v in checks.values() if isinstance(v, dict))
    return {"status": "ok" if all_ok else "degraded", "checks": checks}


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------
@app.get("/api/metrics")
async def api_metrics():
    from metrics import snapshot
    return snapshot()


# ---------------------------------------------------------------------------
# RAG evaluation log endpoints
# ---------------------------------------------------------------------------
@app.get("/api/rag/log")
async def rag_eval_log():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.eval_logger import load_rag_log
        return {"entries": load_rag_log(limit=100)}
    except Exception as e:
        logger.exception("Failed to load RAG eval log")
        return {"error": str(e)}


@app.get("/api/rag/stats")
async def rag_eval_stats():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.eval_logger import get_rag_stats
        return get_rag_stats()
    except Exception as e:
        logger.exception("Failed to load RAG eval stats")
        return {"error": str(e)}


@app.post("/api/rag/rate")
async def rag_rate(data: dict):
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.eval_logger import rate_entry
        ok = rate_entry(data.get("timestamp"), data.get("rating"), data.get("followup"))
        return {"ok": ok}
    except Exception as e:
        logger.exception("Failed to rate RAG entry")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Session replay API
# ---------------------------------------------------------------------------
@app.get("/api/sessions")
async def list_sessions():
    from session_store import session_store
    return {"sessions": session_store.list_ids()}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    from session_store import session_store
    data = session_store.get(session_id)
    if data is None:
        return {"error": "session not found"}
    return {"session": data}


# ---------------------------------------------------------------------------
# MCQ API
# ---------------------------------------------------------------------------
@app.get("/api/mcq/taxonomy")
async def mcq_taxonomy():
    from mcq.taxonomy import SUBJECTS, get_topics, is_valid_subject
    return {
        "subjects": list(SUBJECTS.keys()),
        "topics": {s: get_topics(s) for s in SUBJECTS},
    }


@app.get("/api/mcq/coverage")
async def mcq_coverage():
    if not RAG_AVAILABLE:
        return {"error": "RAG not available"}
    try:
        from rag.vector_store import get_collection
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        subjects = set()
        topic_counts = {}
        for m in (results.get("metadatas") or []):
            sub = m.get("subject") or "uncategorized"
            subjects.add(sub)
            topic_counts[sub] = topic_counts.get(sub, 0) + 1
        from mcq.taxonomy import SUBJECTS
        covered = {s: topic_counts.get(s, 0) > 0 for s in SUBJECTS}
        return {"subjects": sorted(subjects), "covered": covered, "chunk_counts": {s: topic_counts.get(s, 0) for s in SUBJECTS}}
    except Exception as e:
        logger.exception("Failed to get MCQ coverage")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Static files & SPA fallback
# ---------------------------------------------------------------------------
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/nyx")
    async def serve_nyx():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/{file_path:path}")
    async def serve_static(file_path: str):
        full_path = os.path.join(FRONTEND_DIST, file_path)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
