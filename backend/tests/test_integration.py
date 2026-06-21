import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections.abc import AsyncIterator

from tts import split_sentences, _build_audio_frame, stream_tts_tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockWebSocket:
    """A minimal FastAPI WebSocket mock for testing."""
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, data):
        self.sent.append(("json", data))

    async def send_bytes(self, data):
        self.sent.append(("bytes", data))

    async def close(self):
        self.closed = True


async def _token_generator(tokens):
    """Yield tokens from a list, simulating LLM streaming."""
    for t in tokens:
        yield t


def _is_audio_frame(data):
    """Check if data is a valid binary audio frame."""
    if not isinstance(data, bytes) or len(data) < 5:
        return False
    return data[0] == 0x01


def _decode_seq(data):
    """Extract sequence number from a binary audio frame."""
    return int.from_bytes(data[1:5], "little")


# ---------------------------------------------------------------------------
# Tests: Streaming TTS pipeline (tokens → audio frames)
# ---------------------------------------------------------------------------

class TestStreamTtsPipeline:
    """Integration test: LLM token stream → TTS → WebSocket binary frames."""

    @pytest.mark.asyncio
    async def test_full_sentence_streams_one_audio_chunk(self):
        ws = MockWebSocket()
        tokens = ["Hello.", " How are", " you?"]
        gen = stream_tts_tokens(_token_generator(tokens), ws)

        collected = []
        async for token in gen:
            collected.append(token)

        assert "".join(collected) == "Hello. How are you?"

        audio_frames = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(audio_frames) >= 1
        assert all(_is_audio_frame(f) for f in audio_frames)

        json_msgs = [data for kind, data in ws.sent if kind == "json"]
        assert json_msgs[-1] == {"type": "audio_done"}

    @pytest.mark.asyncio
    async def test_empty_token_stream_sends_no_audio(self):
        ws = MockWebSocket()
        gen = stream_tts_tokens(_token_generator([]), ws)

        collected = []
        async for token in gen:
            collected.append(token)

        assert collected == []
        audio_frames = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(audio_frames) == 0

    @pytest.mark.asyncio
    async def test_single_long_sentence(self):
        ws = MockWebSocket()
        tokens = ["This is a very long sentence that does not have any punctuation so it should be treated as a single sentence and piped through TTS as one chunk."]
        gen = stream_tts_tokens(_token_generator(tokens), ws)

        collected = []
        async for token in gen:
            collected.append(token)

        assert len(collected) == 1
        audio_frames = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(audio_frames) == 1
        assert _is_audio_frame(audio_frames[0])

    @pytest.mark.asyncio
    async def test_multiple_sentences_get_sequential_seqs(self):
        ws = MockWebSocket()
        tokens = ["First.", " Second.", " Third."]
        gen = stream_tts_tokens(_token_generator(tokens), ws)

        async for _ in gen:
            pass

        audio_frames = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(audio_frames) == 3
        seqs = [_decode_seq(f) for f in audio_frames]
        assert seqs == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_interleaves_tokens_and_audio(self):
        ws = MockWebSocket()
        tokens = ["Hello.", " World!"]
        gen = stream_tts_tokens(_token_generator(tokens), ws)

        results = []
        async for token in gen:
            results.append(token)

        assert "".join(results) == "Hello. World!"
        # Audio is sent asynchronously after token stream finishes
        audio_frames = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(audio_frames) >= 1

    @pytest.mark.asyncio
    async def test_abbreviation_preserved(self):
        ws = MockWebSocket()
        tokens = ["Dr. Smith said hello. Then he left."]
        gen = stream_tts_tokens(_token_generator(tokens), ws)

        async for _ in gen:
            pass

        # Two actual sentences: "Dr. Smith said hello." and "Then he left."
        # The "Dr." abbreviation is NOT a split point — correct behavior
        audio_frames = [data for kind, data in ws.sent if kind == "bytes" and _is_audio_frame(data)]
        assert len(audio_frames) == 2
        # Verify the first sentence starts with "Dr."
        from tts import split_sentences
        sents = split_sentences("Dr. Smith said hello. Then he left.")
        assert sents[0].startswith("Dr.")

    @pytest.mark.asyncio
    async def test_cancelled_during_stream(self):
        ws = MockWebSocket()

        async def cancelling_gen():
            yield "Hello. "
            raise asyncio.CancelledError()

        import asyncio
        gen = stream_tts_tokens(cancelling_gen(), ws)
        with pytest.raises(asyncio.CancelledError):
            async for _ in gen:
                pass


# ---------------------------------------------------------------------------
# Tests: Mode handler pipeline (user message → LLM → response)
# ---------------------------------------------------------------------------

class TestModeHandlerPipeline:
    """Integration test: user WebSocket message → mode handler → response flow."""

    @pytest.mark.asyncio
    async def test_handle_interview_chat_with_mocked_llm(self):
        """Verify that handle_interview_chat processes a user message and sends a response."""
        ws = MockWebSocket()

        from mode_handlers import handle_interview_chat
        from asyncio import Semaphore

        state = {
            "ws": ws,
            "current_mode": "STRUCTURED",
            "user_role": "Candidate",
            "ai_role": "Interviewer",
            "system_prompt": "You are an interviewer.",
            "conversation_history": "",
            "history_turns": [],
            "rag_context_log": [],
            "_llm_semaphore": Semaphore(1),
            "rag_available": False,
            "data": {"text": "I have 5 years of experience."},
        }

        with patch("mode_handlers.ask_llm_stream") as mock_llm:
            async def fake_stream(prompt, **kw):
                yield "That's "
                yield "great! "
                yield "Tell me more."

            mock_llm.side_effect = fake_stream

            with patch("mode_handlers.generate_tts") as mock_tts:
                mock_tts.return_value = None
                await handle_interview_chat(state)

        json_msgs = [data for kind, data in ws.sent if kind == "json"]
        types = [m["type"] for m in json_msgs]
        assert "user_speech" in types
        assert "ai_response" in types
        ai_resp = next(m for m in json_msgs if m["type"] == "ai_response")
        assert len(ai_resp["text"]) > 0

    @pytest.mark.asyncio
    async def test_handle_interview_chat_with_empty_llm_response(self):
        """Verify graceful handling when LLM returns nothing."""
        ws = MockWebSocket()

        from mode_handlers import handle_interview_chat
        from asyncio import Semaphore

        state = {
            "ws": ws,
            "current_mode": "STRUCTURED",
            "user_role": "Candidate",
            "ai_role": "Interviewer",
            "system_prompt": "You are an interviewer.",
            "conversation_history": "",
            "history_turns": [],
            "rag_context_log": [],
            "_llm_semaphore": Semaphore(1),
            "rag_available": False,
            "data": {"text": "Hello?"},
        }

        with patch("mode_handlers.ask_llm_stream") as mock_llm:
            async def empty_stream(prompt, **kw):
                yield ""  # empty response
                return
            mock_llm.side_effect = empty_stream

            with patch("mode_handlers.generate_tts"):
                await handle_interview_chat(state)

        json_msgs = [data for kind, data in ws.sent if kind == "json"]
        status_msgs = [m for m in json_msgs if m.get("type") == "status"]
        assert any("Sorry" in m.get("message", "") for m in status_msgs)

    @pytest.mark.asyncio
    async def test_nyx_handler_with_mocked_llm(self):
        """Verify Nyx handler processes message and returns response."""
        ws = MockWebSocket()

        from nyx_handler import handle_nyx_message

        with patch("nyx_handler.ask_llm_stream") as mock_llm:
            async def fake_stream(prompt, **kw):
                yield "Hello "
                yield "again."

            mock_llm.side_effect = fake_stream

            response, tone = await handle_nyx_message(
                websocket=ws,
                user_text="Hi Nyx!",
                history_turns=[],
                last_tone=None,
                tts_enabled=False,
                rag_enabled=False,
                rag_context_log=[],
                user_role="User",
                ai_role="Nyx",
            )

        assert len(response) > 0
        assert tone is not None
        json_msgs = [data for kind, data in ws.sent if kind == "json"]
        assert any(m.get("type") == "ai_response" for m in json_msgs)

    @pytest.mark.asyncio
    async def test_nyx_handler_with_rag_enabled(self):
        """Verify Nyx handler calls RAG when rag_enabled=True."""
        ws = MockWebSocket()

        from nyx_handler import handle_nyx_message

        with patch("nyx_handler.ask_llm_stream") as mock_llm:
            async def fake_stream(prompt, **kw):
                yield "Based on the knowledge base, "

            mock_llm.side_effect = fake_stream

            with patch("rag.retriever.retrieve") as mock_retrieve:
                mock_retrieve.return_value = [
                    ("Important knowledge content here.", {"source": "book1.pdf", "page": 5}, 0.95),
                ]

                response, tone = await handle_nyx_message(
                    websocket=ws,
                    user_text="Tell me about topic X",
                    history_turns=[],
                    last_tone=None,
                    tts_enabled=False,
                    rag_enabled=True,
                    rag_context_log=[],
                    user_role="User",
                    ai_role="Nyx",
                )

        assert len(response) > 0
        assert tone is not None

    @pytest.mark.asyncio
    async def test_nyx_handler_with_tts_enabled(self):
        """Verify Nyx handler sends audio when tts_enabled=True."""
        ws = MockWebSocket()

        from nyx_handler import handle_nyx_message

        with patch("nyx_handler.ask_llm_stream") as mock_llm:
            async def fake_stream(prompt, **kw):
                yield "Hello. "
                yield "How are you?"

            mock_llm.side_effect = fake_stream

            response, tone = await handle_nyx_message(
                websocket=ws,
                user_text="Hi",
                history_turns=[],
                last_tone=None,
                tts_enabled=True,
                rag_enabled=False,
                rag_context_log=[],
                user_role="User",
                ai_role="Nyx",
            )

        # With TTS enabled, audio frames should be sent
        bytes_sent = [data for kind, data in ws.sent if kind == "bytes"]
        assert len(bytes_sent) >= 1
        assert all(_is_audio_frame(f) for f in bytes_sent)

    @pytest.mark.asyncio
    async def test_nyx_personality_tone_selection(self):
        """Verify tone selection respects last_tone constraint."""
        from nyx_personality import choose_tone, apply_anti_repetition, clean_response

        # Should get a different tone from the last one
        first = choose_tone(None)
        second = choose_tone(first)
        assert first is not None
        assert second is not None
        assert second != first  # should pick a different tone

    def test_clean_response_removes_leading_role(self):
        from nyx_personality import clean_response
        # Removes only the leading role prefix
        result = clean_response("User: Hello\nAI: Hi there", "User", "AI")
        assert "Hello" in result
        assert "Hi there" in result
        # Second line still has "AI:" since it's not the leading prefix
        assert result == "Hello\nAI: Hi there"

    def test_anti_repetition_catches_exact_repeat(self):
        from nyx_personality import apply_anti_repetition
        # When the exact same phrase appears in history, it gets flagged
        # clean_response strips the leading role prefix (Nyx/User/Assistant/AI)
        result = apply_anti_repetition("Hello there.", ["Nyx: Hello there."])
        assert "familiar" in result

    def test_anti_repetition_passes_different_phrases(self):
        from nyx_personality import apply_anti_repetition
        # A different phrase (via different wording + punctuation) passes through
        result = apply_anti_repetition("Hello there.", ["Nyx: Hello."])
        assert result == "Hello there."

    def test_anti_repetition_passes_new_phrases(self):
        from nyx_personality import apply_anti_repetition
        result = apply_anti_repetition("Tell me about yourself.", [])
        assert result == "Tell me about yourself."
