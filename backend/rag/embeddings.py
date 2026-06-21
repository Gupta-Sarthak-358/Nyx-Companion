import threading

import numpy as np

_model = None
_model_lock = threading.Lock()


def get_embedding_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                import torch
                from config import EMBEDDING_MODEL, EMBEDDING_DEVICE
                device = EMBEDDING_DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")
                from log_utils import logger
                logger.info("Loading embedding model %s on %s", EMBEDDING_MODEL, device)
                _model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    return _model


def embed_texts(texts):
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(embeddings, dtype=np.float32)


def embed_query(text):
    model = get_embedding_model()
    emb = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    return np.array(emb, dtype=np.float32)
