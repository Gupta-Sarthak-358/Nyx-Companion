import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from tts import split_sentences, _run_piper, _build_audio_frame
from collections.abc import AsyncIterator


class TestSplitSentences:
    def test_simple_sentences(self):
        assert split_sentences("Hello. How are you?") == ["Hello.", "How are you?"]

    def test_single_sentence(self):
        assert split_sentences("Hello world.") == ["Hello world."]

    def test_no_punctuation(self):
        assert split_sentences("Hello world") == ["Hello world"]

    def test_abbreviations_preserved(self):
        result = split_sentences("Dr. Smith said hello. Then he left.")
        assert result == ["Dr. Smith said hello.", "Then he left."]

    def test_decimal_preserved(self):
        result = split_sentences("The value is 3.14. That is correct.")
        assert result == ["The value is 3.14.", "That is correct."]

    def test_version_preserved(self):
        result = split_sentences("Upgrade to v3.2.1. It fixes bugs.")
        assert result == ["Upgrade to v3.2.1.", "It fixes bugs."]

    def test_exclamation_split(self):
        result = split_sentences("Wow! Amazing!")
        assert result == ["Wow!", "Amazing!"]

    def test_question_split(self):
        result = split_sentences("Are you sure? I doubt it.")
        assert result == ["Are you sure?", "I doubt it."]

    def test_multiple_abbreviations(self):
        result = split_sentences("Prof. Jones and Dr. Lee collaborated. They published in Jan. 2024.")
        assert result == ["Prof. Jones and Dr. Lee collaborated.", "They published in Jan. 2024."]

    def test_e_g_preserved(self):
        result = split_sentences("Use tools e.g. hammers. They are useful.")
        assert result == ["Use tools e.g. hammers.", "They are useful."]

    def test_empty_text(self):
        assert split_sentences("") == [""]

    def test_only_whitespace(self):
        result = split_sentences("   ")
        assert len(result) == 1
        assert result[0].strip() == ""


class TestRunPiper:
    def test_empty_text(self):
        assert _run_piper("") == b""

    def test_whitespace_text(self):
        assert _run_piper("   ") == b""

    def test_short_text_returns_bytes(self):
        result = _run_piper("Hello.")
        assert isinstance(result, bytes)


class TestBuildAudioFrame:
    def test_frame_structure(self):
        frame = _build_audio_frame(b"\x00\x01\x02", seq=5)
        # 5-byte header: type(0x01) + seq(5 as u32 LE)
        assert frame[0] == 0x01
        assert int.from_bytes(frame[1:5], "little") == 5
        assert frame[5:] == b"\x00\x01\x02"

    def test_empty_audio(self):
        frame = _build_audio_frame(b"", seq=0)
        assert len(frame) == 5
        assert frame[0] == 0x01


class TestStreamTtsTokens:
    @pytest.mark.asyncio
    async def test_yields_tokens(self):
        from tts import stream_tts_tokens

        async def mock_gen():
            yield "Hello. "
            yield "How are you?"

        class MockWS:
            def __init__(self):
                self.sent = []

            async def send_bytes(self, data):
                self.sent.append(data)

            async def send_json(self, data):
                self.sent.append(data)

        ws = MockWS()
        collected = []
        async for token in stream_tts_tokens(mock_gen(), ws):
            collected.append(token)

        assert "".join(collected) == "Hello. How are you?"
        # Should have sent audio_done at end
        assert any(s == {"type": "audio_done"} for s in ws.sent)

    @pytest.mark.asyncio
    async def test_empty_token_stream(self):
        from tts import stream_tts_tokens

        async def empty_gen():
            return
            yield

        class MockWS:
            def __init__(self):
                self.sent = []

            async def send_bytes(self, data):
                self.sent.append(data)

            async def send_json(self, data):
                self.sent.append(data)

        ws = MockWS()
        collected = []
        async for token in stream_tts_tokens(empty_gen(), ws):
            collected.append(token)

        assert collected == []
