"""Tests for MCQ prompt generation and JSON validation/retry.

Run from backend/:
    PYTHONPATH=. pytest tests/test_mcq_prompt.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestBuildTopicQuery:

    def test_with_topic(self):
        from mcq.mcq_prompt import _build_topic_query
        assert _build_topic_query("dsa", "trees") == "explain the concept of trees in dsa with an example"

    def test_without_topic(self):
        from mcq.mcq_prompt import _build_topic_query
        assert _build_topic_query("verbal", None) == "define vocabulary grammar reading comprehension passage"


class TestDifficultyInstruction:

    def test_level_1(self):
        from mcq.mcq_prompt import _difficulty_instruction
        ins = _difficulty_instruction(1)
        assert "Basic recall" in ins

    def test_level_3(self):
        from mcq.mcq_prompt import _difficulty_instruction
        ins = _difficulty_instruction(3)
        assert "Applied understanding" in ins

    def test_level_5(self):
        from mcq.mcq_prompt import _difficulty_instruction
        ins = _difficulty_instruction(5)
        assert "Expert-level" in ins

    def test_fallback_to_mid(self):
        from mcq.mcq_prompt import _difficulty_instruction
        ins = _difficulty_instruction(99)
        assert "Applied understanding" in ins


class TestValidateQuestion:

    def test_valid(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "What is 2+2?", "options": ["1", "2", "3", "4"], "correct_index": 3, "explanation": "Because math."}
        assert _validate_question(data) is None

    def test_not_a_dict(self):
        from mcq.mcq_prompt import _validate_question
        assert _validate_question("string") is not None

    def test_missing_question(self):
        from mcq.mcq_prompt import _validate_question
        data = {"options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "x"}
        assert "question" in _validate_question(data)

    def test_empty_question(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "  ", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "x"}
        assert "question" in _validate_question(data)

    def test_wrong_option_count(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A"], "correct_index": 0, "explanation": "x"}
        err = _validate_question(data)
        assert err and "4" in err

    def test_empty_option(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "", "C", "D"], "correct_index": 0, "explanation": "x"}
        assert _validate_question(data) is not None

    def test_bad_correct_index_type(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "B", "C", "D"], "correct_index": "0", "explanation": "x"}
        assert _validate_question(data) is not None

    def test_correct_index_out_of_range(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "B", "C", "D"], "correct_index": 5, "explanation": "x"}
        assert _validate_question(data) is not None

    def test_correct_index_negative(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "B", "C", "D"], "correct_index": -1, "explanation": "x"}
        assert _validate_question(data) is not None

    def test_duplicate_options_rejected(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "A", "C", "D"], "correct_index": 0, "explanation": "x"}
        err = _validate_question(data)
        assert err is not None
        assert "Duplicate" in err

    def test_case_insensitive_duplicate(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "a", "C", "D"], "correct_index": 0, "explanation": "x"}
        err = _validate_question(data)
        assert err is not None
        assert "Duplicate" in err

    def test_missing_explanation(self):
        from mcq.mcq_prompt import _validate_question
        data = {"question": "Q?", "options": ["A", "B", "C", "D"], "correct_index": 0}
        assert "explanation" in _validate_question(data)


class TestParseJson:

    def test_direct_json(self):
        from mcq.mcq_prompt import _parse_json
        raw = json.dumps({"question": "test", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "e"})
        result = _parse_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_markdown_fence_json(self):
        from mcq.mcq_prompt import _parse_json
        raw = "```json\n{\"question\": \"test\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_index\": 0, \"explanation\": \"e\"}\n```"
        result = _parse_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_markdown_fence_no_lang(self):
        from mcq.mcq_prompt import _parse_json
        raw = "```\n{\"question\": \"test\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_index\": 0, \"explanation\": \"e\"}\n```"
        result = _parse_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_curly_brace_extraction(self):
        from mcq.mcq_prompt import _parse_json
        raw = "Some text here {\"question\": \"test\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_index\": 0, \"explanation\": \"e\"} and trailing"
        result = _parse_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_non_json_returns_none(self):
        from mcq.mcq_prompt import _parse_json
        assert _parse_json("not json at all") is None


FAKE_QUESTION = {
    "question": "What is a binary search tree?",
    "options": ["A tree with at most 2 children", "A sorted tree", "A tree", "Wrong"],
    "correct_index": 0,
    "explanation": "A BST has at most 2 children per node.",
}

FAKE_RESULTS = [
    ("A BST is a tree with two children.", {"source": "book.pdf", "page": "10"}, 0.95),
    ("Trees are hierarchical.", {"source": "book.pdf", "page": "11"}, 0.85),
]


class TestGenerateMCQ:

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_success_path(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        mock_ask_llm.return_value = json.dumps(FAKE_QUESTION)

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)

        assert result is not None
        assert result["question"] == FAKE_QUESTION["question"]
        assert result["subject"] == "dsa"
        assert result["topic"] == "trees"
        assert result["difficulty"] == 3
        assert len(result["options"]) == 4
        assert result["correct_index"] == 0
        assert "source_chunks" in result
        mock_retrieve.assert_called_once_with(
            "explain the concept of trees in dsa with an example",
            top_k=15,
            where_filter={"$and": [{"subject": "dsa"}, {"section": {"$ne": "front_matter"}}, {"topic": "trees"}]},
        )

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_no_topic_success(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        mock_ask_llm.return_value = json.dumps(FAKE_QUESTION)

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("verbal", topic=None, difficulty=1)

        assert result is not None
        assert result["subject"] == "verbal"
        assert result["topic"] is None
        assert result["difficulty"] == 1
        mock_retrieve.assert_called_once_with(
            "define vocabulary grammar reading comprehension passage",
            top_k=15,
            where_filter={"$and": [{"subject": "verbal"}, {"section": {"$ne": "front_matter"}}]},
        )

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    async def test_no_results_returns_none(self, mock_retrieve):
        mock_retrieve.return_value = []

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is None

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_retry_on_validation_fail(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        bad_json = json.dumps({"question": "Q", "options": ["A"], "correct_index": 0, "explanation": "e"})
        mock_ask_llm.side_effect = [bad_json, json.dumps(FAKE_QUESTION)]

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is not None
        assert mock_ask_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_both_attempts_fail_returns_none(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        bad_json = json.dumps({"question": "Q", "options": ["A"], "correct_index": 0, "explanation": "e"})
        mock_ask_llm.side_effect = [bad_json, "invalid garbage"]

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is None
        assert mock_ask_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_handles_retrieve_exception(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.side_effect = RuntimeError("chroma down")

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is None

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_llm_returns_markdown_fence(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        raw = "```json\n" + json.dumps(FAKE_QUESTION) + "\n```"
        mock_ask_llm.return_value = raw

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is not None
        assert result["question"] == FAKE_QUESTION["question"]

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_second_attempt_has_stricter_prompt(self, mock_ask_llm, mock_retrieve):
        mock_retrieve.return_value = FAKE_RESULTS
        mock_ask_llm.side_effect = ["invalid", json.dumps(FAKE_QUESTION)]

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is not None
        second_prompt = mock_ask_llm.call_args_list[1][0][0]
        assert "IMPORTANT" in second_prompt

    @pytest.mark.asyncio
    @patch("mcq.mcq_prompt.retrieve")
    @patch("mcq.mcq_prompt.ask_llm")
    async def test_context_trimmed_by_char_budget(self, mock_ask_llm, mock_retrieve):
        long_result = ("A" * 1000, {"source": "big.pdf", "page": "1"}, 0.99)
        mock_retrieve.return_value = [long_result]
        mock_ask_llm.return_value = json.dumps(FAKE_QUESTION)

        from mcq.mcq_prompt import generate_mcq
        result = await generate_mcq("dsa", topic="trees", difficulty=3)
        assert result is not None
        prompt = mock_ask_llm.call_args[0][0]
        assert "big.pdf" in prompt
