from .taxonomy import is_valid_subject

INITIAL_DIFFICULTY = 3
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
STREAK_TO_UP = 2
STREAK_TO_DOWN = 1


class AdaptiveDifficulty:
    """Per-subject adaptive difficulty state machine.

    Up-2/down-1 ladder:
    - 2 consecutive correct answers → difficulty +1 (capped at 5, streak resets)
    - 1 wrong answer → difficulty -1 (floored at 1, streak resets)
    """

    def __init__(self, state: dict | None = None):
        if state:
            self._subjects = _validate_state(state)
        else:
            self._subjects = {}

    def _ensure_subject(self, subject: str):
        if not is_valid_subject(subject):
            raise ValueError(f"Unknown subject: {subject}")
        if subject not in self._subjects:
            self._subjects[subject] = {
                "current_difficulty": INITIAL_DIFFICULTY,
                "streak_correct": 0,
                "streak_wrong": 0,
            }

    def get_difficulty(self, subject: str) -> int:
        self._ensure_subject(subject)
        return self._subjects[subject]["current_difficulty"]

    def record_answer(self, subject: str, correct: bool) -> dict:
        """Record an answer and return updated state for this subject."""
        self._ensure_subject(subject)
        s = self._subjects[subject]

        if correct:
            s["streak_correct"] += 1
            s["streak_wrong"] = 0
            if s["streak_correct"] >= STREAK_TO_UP:
                s["current_difficulty"] = min(MAX_DIFFICULTY, s["current_difficulty"] + 1)
                s["streak_correct"] = 0
        else:
            s["streak_wrong"] += 1
            s["streak_correct"] = 0
            if s["streak_wrong"] >= STREAK_TO_DOWN:
                s["current_difficulty"] = max(MIN_DIFFICULTY, s["current_difficulty"] - 1)
                s["streak_wrong"] = 0

        return dict(s)

    def get_state(self) -> dict:
        return dict(self._subjects)

    def load_state(self, state: dict):
        self._subjects = _validate_state(state)


def _validate_state(state: dict) -> dict:
    validated = {}
    for subject, data in state.items():
        if not is_valid_subject(subject):
            continue
        validated[subject] = {
            "current_difficulty": max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, data.get("current_difficulty", INITIAL_DIFFICULTY))),
            "streak_correct": max(0, data.get("streak_correct", 0)),
            "streak_wrong": max(0, data.get("streak_wrong", 0)),
        }
    return validated
