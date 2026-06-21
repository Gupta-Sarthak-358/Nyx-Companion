import copy
import threading

from log_utils import logger


class SessionStore:
    """In-memory session store. Sessions are lost on backend restart."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def get(self, session_id):
        with self._lock:
            data = self._sessions.get(session_id)
            return copy.deepcopy(data) if data else None

    def save(self, session_id, data):
        with self._lock:
            self._sessions[session_id] = copy.deepcopy(data)

    def delete(self, session_id):
        with self._lock:
            self._sessions.pop(session_id, None)

    @property
    def active_count(self):
        with self._lock:
            return len(self._sessions)

    def list_ids(self):
        with self._lock:
            return list(self._sessions.keys())


session_store = SessionStore()


SESSION_KEYS = [
    "history_turns",
    "session_evals",
    "rag_context_log",
    "current_mode",
    "conversation_history",
    "system_prompt",
    "user_role",
    "ai_role",
    "is_scenario_setup_needed",
    "nyx_last_tone",
    "nyx_tts_enabled",
    "nyx_rag_enabled",
    "nyx_rag_context_log",
    "session_acoustic_hits",
]


def pack_session(**kwargs):
    return {k: v for k, v in kwargs.items() if k in SESSION_KEYS}


def unpack_session(data, defaults):
    if not data:
        return defaults
    result = dict(defaults)
    for k in SESSION_KEYS:
        if k in data:
            result[k] = copy.deepcopy(data[k])
    return result
