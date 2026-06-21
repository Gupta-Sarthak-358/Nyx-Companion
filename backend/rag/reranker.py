import threading

import torch

from log_utils import logger

_reranker = None
_reranker_lock = threading.Lock()
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-2-v2"


def get_reranker():
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info("Loading cross-encoder %s on %s", RERANKER_MODEL, device)
                _reranker = CrossEncoder(RERANKER_MODEL, device=device)
    return _reranker


def rerank(query, candidates, top_k=5):
    """
    Re-rank a list of (document, metadata, score) tuples using a cross-encoder.
    Returns top_k re-ranked results with updated scores.
    """
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [(query, doc) for doc, _, _ in candidates]
    scores = reranker.predict(pairs, show_progress_bar=False)

    scored = list(zip(scores, candidates))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, (doc, meta, _orig_score) in scored[:top_k]:
        results.append((doc, meta, float(score)))

    return results
