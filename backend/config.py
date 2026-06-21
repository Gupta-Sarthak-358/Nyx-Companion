import os

BACKEND_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: str = os.path.dirname(BACKEND_DIR)

# LLM
LLAMA_URL: str = os.environ.get("LLAMA_URL", "http://localhost:8080/completion")

# TTS
PIPER_BINARY: str = os.environ.get("PIPER_BINARY", os.path.join(BACKEND_DIR, "piper", "piper"))
PIPER_MODEL: str = os.environ.get(
    "PIPER_MODEL",
    os.path.join(os.environ.get("HOME", "/home/satvi"), "RAG_PHASE_1", "models", "en_US-amy-medium.onnx"),
)

# STT
WHISPER_MODEL_SIZE: str = os.environ.get("WHISPER_MODEL_SIZE", "small")

# RAG / Embeddings
CHROMA_DB_DIR: str = os.environ.get(
    "CHROMA_DB_DIR",
    os.path.join(PROJECT_ROOT, "knowledge", "chroma_db"),
)
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DEVICE: str = os.environ.get("EMBEDDING_DEVICE", "")  # empty = auto-detect

# Paths
PROMPT_PATH: str = os.environ.get("PROMPT_PATH", os.path.join(BACKEND_DIR, "prompt.txt"))
FRONTEND_DIST: str = os.environ.get("FRONTEND_DIST", os.path.join(PROJECT_ROOT, "frontend", "dist"))
PROCESSED_DIR: str = os.environ.get("PROCESSED_DIR", os.path.join(PROJECT_ROOT, "knowledge", "processed"))
BOOKS_DIR: str = os.environ.get("BOOKS_DIR", os.path.join(PROJECT_ROOT, "knowledge", "books"))
