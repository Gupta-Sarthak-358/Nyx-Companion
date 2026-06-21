import json
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import WebSocket


class WSMessage(BaseModel):
    type: str = Field(alias="type")
    text: Optional[str] = None
    data: Optional[str] = None
    session_id: Optional[str] = None
    mode: Optional[str] = None
    description: Optional[str] = None
    tts_enabled: Optional[bool] = None
    rag_enabled: Optional[bool] = None
    enabled: Optional[bool] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    question_id: Optional[str] = None
    selected_index: Optional[int] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"start", "audio", "chat_message", "retry", "nudge", "end_interview", "toggle_tts", "toggle_rag",
                    "mcq_start", "mcq_answer", "mcq_next", "mcq_end"}
        if v not in allowed:
            raise ValueError(f"Unknown message type: {v}")
        return v


def parse_ws_message(data: str | bytes, ws: WebSocket) -> WSMessage | None:
    """Parse and validate an incoming WebSocket message. Returns None on parse/validation failure."""
    try:
        if isinstance(data, bytes):
            raw = json.loads(data.decode())
        else:
            raw = json.loads(data)
        return WSMessage(**raw)
    except (json.JSONDecodeError, ValueError) as e:
        from log_utils import logger
        logger.warning("WS message validation failed: %s", e)
        return None
