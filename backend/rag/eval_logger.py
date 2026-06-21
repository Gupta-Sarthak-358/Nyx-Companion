import json
import os
import threading
from datetime import datetime, timezone

_log_path = None
_ratings_path = None
_lock = threading.Lock()


def _ensure_path():
    global _log_path
    if _log_path is None:
        from config import BACKEND_DIR
        _log_path = os.path.join(BACKEND_DIR, "rag_eval_log.jsonl")
        os.makedirs(os.path.dirname(_log_path), exist_ok=True)
    return _log_path


def _ensure_ratings_path():
    global _ratings_path
    if _ratings_path is None:
        from config import BACKEND_DIR
        _ratings_path = os.path.join(BACKEND_DIR, "rag_ratings.jsonl")
    return _ratings_path


def _load_ratings():
    """Return a dict mapping timestamp -> {rating, followup}."""
    path = _ensure_ratings_path()
    if not os.path.exists(path):
        return {}
    ratings = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                ratings[r["timestamp"]] = r
    return ratings


def log_rag_turn(query, chunks, response):
    """Append a {query, chunks, response} triplet to the JSONL evaluation log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "chunks": [
            {
                "text": doc[:300],
                "source": meta.get("source", "?"),
                "page": meta.get("page"),
                "score": round(score, 4),
            }
            for doc, meta, score in (chunks or [])
        ],
        "response": response,
        "rating": None,
        "followup": None,
    }
    path = _ensure_path()
    with _lock:
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    return entry


def rate_entry(timestamp, rating, followup=None):
    """Record a thumbs-up/down rating for a log entry by timestamp."""
    if rating not in ("thumbs_up", "thumbs_down"):
        return False
    entry = {
        "timestamp": timestamp,
        "rating": rating,
        "followup": followup,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    path = _ensure_ratings_path()
    with _lock:
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    return True


def load_rag_log(limit=50):
    """Return the most recent `limit` entries from the evaluation log, merged with ratings."""
    path = _ensure_path()
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    ratings = _load_ratings()
    for e in entries:
        ts = e.get("timestamp")
        if ts in ratings:
            e["rating"] = ratings[ts]["rating"]
            e["followup"] = ratings[ts].get("followup")
    return entries[-limit:]


def get_rag_stats():
    """Return aggregate stats over the evaluation log."""
    entries = load_rag_log(limit=10000)
    if not entries:
        return {"total": 0, "avg_chunks": 0, "avg_query_len": 0, "avg_response_len": 0, "thumbs_up": 0, "thumbs_down": 0}
    thumbs_up = sum(1 for e in entries if e.get("rating") == "thumbs_up")
    thumbs_down = sum(1 for e in entries if e.get("rating") == "thumbs_down")
    return {
        "total": len(entries),
        "avg_chunks": round(sum(len(e.get("chunks", [])) for e in entries) / len(entries), 1),
        "avg_query_len": round(sum(len(e["query"]) for e in entries) / len(entries), 0),
        "avg_response_len": round(sum(len(e.get("response", "")) for e in entries) / len(entries), 0),
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
    }
