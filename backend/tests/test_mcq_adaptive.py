"""Tests for the MCQ adaptive difficulty engine.

Run from backend/:
    PYTHONPATH=. pytest tests/test_mcq_adaptive.py -v
"""

import pytest
from mcq.adaptive import AdaptiveDifficulty, INITIAL_DIFFICULTY, MIN_DIFFICULTY, MAX_DIFFICULTY
from mcq.taxonomy import SUBJECTS


class TestAdaptiveDifficulty:

    def test_starts_at_midpoint(self):
        ad = AdaptiveDifficulty()
        assert ad.get_difficulty("dsa") == INITIAL_DIFFICULTY

    def test_two_correct_bumps_up(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        assert ad.get_difficulty("dsa") == INITIAL_DIFFICULTY + 1

    def test_one_wrong_drops_down(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        assert ad.get_difficulty("dsa") == 4
        ad.record_answer("dsa", correct=False)
        assert ad.get_difficulty("dsa") == 3

    def test_clamps_at_minimum(self):
        ad = AdaptiveDifficulty()
        for _ in range(20):
            ad.record_answer("dsa", correct=False)
        assert ad.get_difficulty("dsa") == MIN_DIFFICULTY

    def test_clamps_at_maximum(self):
        ad = AdaptiveDifficulty()
        for _ in range(20):
            ad.record_answer("dsa", correct=True)
        assert ad.get_difficulty("dsa") == MAX_DIFFICULTY

    def test_subjects_tracked_independently(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        ad.record_answer("verbal", correct=False)
        assert ad.get_difficulty("dsa") == INITIAL_DIFFICULTY + 1
        assert ad.get_difficulty("verbal") == INITIAL_DIFFICULTY - 1

    def test_get_state_roundtrip(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        state = ad.get_state()
        ad2 = AdaptiveDifficulty(state=state)
        assert ad2.get_difficulty("dsa") == ad.get_difficulty("dsa")

    def test_load_state(self):
        ad = AdaptiveDifficulty()
        state = {"dsa": {"current_difficulty": 5, "streak_correct": 0, "streak_wrong": 0}}
        ad.load_state(state)
        assert ad.get_difficulty("dsa") == 5

    def test_load_state_clamps_out_of_range(self):
        ad = AdaptiveDifficulty()
        state = {"dsa": {"current_difficulty": 99, "streak_correct": -5, "streak_wrong": 0}}
        ad.load_state(state)
        assert ad.get_difficulty("dsa") == MAX_DIFFICULTY
        assert ad._subjects["dsa"]["streak_correct"] == 0

    def test_load_state_ignores_unknown_subject(self):
        ad = AdaptiveDifficulty()
        state = {"nonexistent": {"current_difficulty": 3, "streak_correct": 0, "streak_wrong": 0}}
        ad.load_state(state)
        assert "nonexistent" not in ad._subjects

    def test_unknown_subject_raises(self):
        ad = AdaptiveDifficulty()
        with pytest.raises(ValueError, match="Unknown subject"):
            ad.get_difficulty("nonexistent")

    def test_streak_resets_on_correct_after_wrong(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=False)
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        assert ad.get_difficulty("dsa") == INITIAL_DIFFICULTY

    def test_streak_resets_on_wrong_after_correct(self):
        ad = AdaptiveDifficulty()
        ad.record_answer("dsa", correct=True)
        ad.record_answer("dsa", correct=True)
        prev = ad.get_difficulty("dsa")
        ad.record_answer("dsa", correct=False)
        assert ad.get_difficulty("dsa") == prev - 1

    def test_record_answer_returns_state_snapshot(self):
        ad = AdaptiveDifficulty()
        result = ad.record_answer("dsa", correct=True)
        assert "current_difficulty" in result
        assert "streak_correct" in result
        assert "streak_wrong" in result

    def test_all_subjects_start_independently(self):
        ad = AdaptiveDifficulty()
        for subject in SUBJECTS:
            assert ad.get_difficulty(subject) == INITIAL_DIFFICULTY


class TestTaxonomy:

    def test_is_valid_subject(self):
        from mcq.taxonomy import is_valid_subject
        assert is_valid_subject("dsa")
        assert not is_valid_subject("nonexistent")

    def test_is_valid_topic(self):
        from mcq.taxonomy import is_valid_topic
        assert is_valid_topic("dsa", "trees")
        assert is_valid_topic("dsa", "backtracking")
        assert is_valid_topic("dsa", "heap_pq")
        assert not is_valid_topic("dsa", "nonexistent")
        assert not is_valid_topic("nonexistent", "anything")

    def test_get_topics(self):
        from mcq.taxonomy import get_topics
        assert "trees" in get_topics("dsa")
        assert "backtracking" in get_topics("dsa")
        assert get_topics("nonexistent") == []

    def test_system_design_is_valid(self):
        from mcq.taxonomy import is_valid_subject, is_valid_topic, get_topics
        assert is_valid_subject("system_design")
        assert is_valid_topic("system_design", "case_studies")
        assert "caching" in get_topics("system_design")
        assert get_topics("system_design") == ["scalability_basics", "databases_at_scale", "caching", "load_balancing", "case_studies"]
