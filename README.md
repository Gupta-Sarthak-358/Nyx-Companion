# Nyx Companion

A fully offline AI learning platform featuring:
- Conversational AI Assistant
- RAG-powered tutoring
- Adaptive MCQ practice
- AI interview simulation
- Voice interaction

Built with React, FastAPI, ChromaDB, Whisper, Piper, and local LLMs.

---

## Modes

| Mode | Pattern | What it does |
|---|---|---|
| **Interview** (4 variants) | AI → User | Asks questions, scores answers on clarity/depth/relevance |
| **Tutor (RAG)** | Knowledge → User | Answers your questions from personal PDFs |
| **Nyx Assistant** | AI ↔ User | Personality-driven chat + voice + knowledge toggle |
| **MCQ Practice** | AI → User | Generates adaptive multiple-choice questions from your PDFs |

### MCQ Practice

Generates questions from 5 subjects using adaptive difficulty:

| Subject | Topics | Source |
|---|---|---|
| **DSA** | arrays, linked_list, stack, queue, hashing, binary_search, sorting, recursion, backtracking, trees, heap_pq, graph, trie, matrix, strings, intervals, bit_manipulation, math, greedy, cyclic_sort, dp | Markdown handbooks |
| **CS Fundamentals** | os, dbms, cn, oop | Silberschatz, Kurose, etc. PDFs |
| **System Design** | scalability_basics, databases_at_scale, caching, load_balancing, case_studies | DDIA, Alex Xu PDFs |
| **Aptitude** | quant_arithmetic, quant_algebra, logical_reasoning, data_interpretation | RS Aggarwal, Arun Sharma PDFs |
| **Verbal** | reading_comprehension, grammar, vocabulary, sentence_correction | Wren & Martin, Word Power Made Easy, SAT/GRE PDFs |

Difficulty adapts per-subject based on streak history. Questions drawn from real PDF content — the model generates fresh questions each time from retrieved chunks, not a fixed question bank.

---

## Stack

- **Frontend**: React (Vite, 4 components + 3 hooks), real-time WebSocket streaming
- **Backend**: FastAPI + WebSockets, Pydantic message validation
- **LLM**: Mistral 7B or Qwen2.5 7B (via `llama-server`, GPU offloaded, 8192 ctx)
- **STT**: `faster-whisper` (small, int8)
- **TTS**: `piper` (amy-medium) — streaming sentence-level generation via binary WebSocket frames
- **RAG**: ChromaDB + `bge-small-en-v1.5` (token-aware 400-token chunks) + cross-encoder re-ranker
- **Metrics**: Rolling p50/p95/p99 latency per operation, exposed at `/api/metrics`
- **All local**: No internet required after initial model download

---

## Quick Start

```bash
cd /home/satvi/RAG_PHASE_1/AI_interview
./run_all.sh
```

Opens at `http://localhost:5000`.

The script auto-detects GPU (`nvidia-smi`), starts `llama-server` with the configured model, builds the frontend, and launches the backend.

---

## Nyx Assistant

The assistant mode with personality, voice, and optional RAG:

- **Knowledge toggle** — queries your PDF vector store, cites sources
- **Voice toggle** — streaming TTS via binary WebSocket frames (no base64 overhead)
- **Mic input** — speak instead of type (Whisper transcription)
- **Personality** — 5 tones (playful, thoughtful, sarcastic, dry, casual), anti-repetition
- **All prompts** managed as YAML files in `backend/prompts/`

---

## Knowledge Management

Add PDFs to `knowledge/books/` per subject subfolder:

```bash
cp my-dsa-book.pdf knowledge/books/dsa/
# Then trigger via UI Knowledge panel, or:
cd backend && PYTHONPATH=. python -m rag.ingest
```

### Subject folders

```
knowledge/books/
├── dsa/                  # Markdown (`.md`) files for structured DSA topics
├── cs_fundamentals/      # OS, DBMS, CN, OOP textbooks
├── system_design/        # DDIA, Alex Xu, system design interview books
├── verbal/               # Grammar, vocabulary, reading comprehension
└── aptitude/             # Quantitative, logical reasoning, data interpretation
```

### Retrieval pipeline

```
Query
  ↓
Embedding Search (bge-small, top-20)
  ↓
Cross-Encoder Reranker (MiniLM, top-5)
  ↓
Session-aware context (tracks previous queries + sources)
  ↓
RAG evaluation log (query → chunks → response)
```

Every RAG query is logged as a `{query, chunks, response}` triplet in `backend/rag_eval_log.jsonl`. View via `/api/rag/log`.

---

## Reliability

- **Retry**: All LLM calls retry 3× with exponential backoff on timeout/5xx/connection error
- **Per-session semaphore**: Each session has its own `asyncio.Semaphore(1)` — no cross-session blocking
- **Rate limiting**: 200ms per-session debounce on WebSocket messages
- **Pydantic validation**: Incoming WebSocket messages validated against `WSMessage` model
- **Logging**: Timestamped structured logs with `logger.exception()`
- **Health check**: Async startup check (doesn't block event loop)
- **Reconnection**: WebSocket auto-reconnects with 1s–15s exponential backoff
- **Session persistence**: State saved to SQLite-backed store, rehydrated on reconnect via `session_id`
- **Model preloading**: Embedding + reranker loaded at startup (not on first query)

---

## Configuration (all optional env vars)

| Variable | Default | Description |
|---|---|---|
| `LLAMA_URL` | `http://localhost:8080/completion` | LLM endpoint |
| `CHROMA_DB_DIR` | `knowledge/chroma_db` | Vector store path |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `EMBEDDING_DEVICE` | auto (cuda/cpu) | Override device |
| `WHISPER_MODEL_SIZE` | `small` | faster-whisper size |
| `PIPER_BINARY` | `backend/piper/piper` | TTS binary |
| `PIPER_MODEL` | `models/en_US-amy-medium.onnx` | TTS voice |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:4173` | Allowed CORS origins |
| `FRONTEND_DIST` | `frontend/dist` | Built frontend |
| `BOOKS_DIR` | `knowledge/books` | PDF drop folder |

---

## Project Structure

```
├── backend/
│   ├── server.py              # Main WS handler — dispatches to mode handlers
│   ├── mode_handlers.py       # Per-mode logic (interview, tutor, conversation)
│   ├── mcq/
│   │   ├── mcq_prompt.py      # MCQ generation: RAG retrieval → prompt → LLM → validate → retry
│   │   ├── taxonomy.py        # Subject/topic definitions + PDF→topic filename mapping
│   │   └── adaptive.py        # Per-subject adaptive difficulty (streak-based)
│   ├── llm_client.py          # LLM client with retry + per-session semaphore
│   ├── config.py              # Env-driven configuration
│   ├── ws_models.py           # Pydantic WebSocket message validation
│   ├── metrics.py             # Rolling latency stats (p50/p95/p99)
│   ├── prompt_loader.py       # YAML prompt loader
│   ├── prompts/               # YAML prompt files (interview, nyx, tutor, nyx_rag)
│   ├── session_store.py       # In-memory session store (lost on restart)
│   ├── nyx_handler.py         # Nyx message handling (shared between WS paths)
│   ├── nyx_personality.py     # Tone selection, anti-repetition, prompt builder
│   ├── tts.py                 # Piper wrapper + binary-frame streaming TTS
│   ├── log_utils.py           # Structured logging
│   ├── tests/                 # 128 tests across all modules
│   └── rag/
│       ├── chunker.py         # PDF → sections → token-aware chunks (400 tok)
│       ├── embeddings.py       # bge-small-en-v1.5 (GPU if available)
│       ├── vector_store.py     # ChromaDB interface
│       ├── retriever.py        # Bi-encoder + cross-encoder pipeline
│       ├── reranker.py         # Cross-encoder (MiniLM-L-2-v2)
│       ├── quality_filter.py   # Dedup + junk rejection
│       ├── compressor.py       # Token-budget-aware context truncation
│       ├── integration.py      # Session-aware RAG prompt builder
│       ├── eval_logger.py      # JSONL query→chunks→response logging
│       ├── watcher.py          # PDF directory watcher (stable-size + retry)
│       └── ingest.py           # Full ingestion pipeline with progress callbacks
├── frontend/src/
│   ├── App.jsx                 # State/effect orchestration
│   ├── useWebSocket.js         # WS lifecycle + binary frame handling
│   ├── useAudioPlayback.js     # Audio queue (capped at 20) + sequenced playback
│   ├── useSpeechRecognition.js # Mic capture + silence detection
│   ├── ModeSelector.jsx        # Setup form component
│   ├── NyxInterface.jsx        # Nyx chat UI component
│   ├── InterviewRoom.jsx       # Video grid + sidebar + controls component
│   ├── KnowledgeBase.jsx       # Knowledge panel modal with progress bar
│   ├── Diagnostics.jsx         # Service health modal (LLM/Whisper/Piper/Chroma)
│   └── DevTools.jsx            # Dev tools: session list, RAG queries, metrics
├── knowledge/
│   ├── books/                  # Drop PDFs here (organized by subject)
│   └── chroma_db/              # Vector store (auto-created)
└── run_all.sh
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| WebSocket | `/ws/interview` | Main session handler (all modes) |
| WebSocket | `/ws/mcq` | MCQ practice mode |
| GET | `/api/knowledge/stats` | RAG chunk/source counts |
| GET | `/api/knowledge/sources` | Source list with page ranges |
| DELETE | `/api/knowledge/sources/{name}` | Remove a source |
| POST | `/api/knowledge/ingest` | Re-ingest all PDFs |
| GET | `/api/knowledge/ingest-progress` | Current ingestion progress |
| POST | `/api/knowledge/upload` | Upload a PDF |
| GET | `/api/rag/log` | RAG evaluation log (last 100 entries) |
| GET | `/api/rag/stats` | RAG aggregate statistics |
| GET | `/api/mcq/taxonomy` | Available subjects and topics |
| POST | `/api/mcq/generate` | Generate an MCQ question |
| GET | `/api/metrics` | Rolling latency statistics |

---

## Tests

```bash
cd backend && PYTHONPATH=. python -m pytest tests/ -v
# 128 tests covering: TTS (19), MCQ prompt (32), RAG pipeline, chunker, adaptive difficulty
```

---

## Model Configuration

Edit `run_all.sh` to switch between models:

```bash
# Mistral 7B (default)
LLAMA_MODEL=mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Qwen2.5 7B (better instruction following)
LLAMA_MODEL=qwen2.5-7b-instruct-q4_k_m.gguf
```

Models must be placed in `~/RAG_PHASE_1/models/`. Qwen2.5 is recommended for MCQ mode due to better adherence to JSON formatting instructions.
