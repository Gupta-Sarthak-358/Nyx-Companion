import re
import math
from collections import Counter

FILLER_WORDS = ["um", "uh", "like", "basically", "actually", "literally", "sort of", "kind of", "you know"]

_EVAL_RE = re.compile(
    r"---EVALUATION---\s*"
    r"CLARITY:\s*(\d+)\s*"
    r"STRUCTURE:\s*(\d+)\s*"
    r"CONFIDENCE:\s*(\d+)\s*"
    r"RELEVANCE:\s*(\d+)\s*"
    r"DEPTH:\s*(\d+)\s*"
    r"SUGGESTION:\s*(.+)",
    re.DOTALL,
)


def parse_evaluation(text):
    m = _EVAL_RE.search(text)
    if not m:
        return None, text
    clean = text[:m.start()].strip()
    return {
        "clarity": int(m.group(1)),
        "structure": int(m.group(2)),
        "confidence": int(m.group(3)),
        "relevance": int(m.group(4)),
        "depth": int(m.group(5)),
        "suggestion": m.group(6).strip(),
    }, clean


def rebuild_history(mode, turns, instruction_template):
    return instruction_template + "\n\n" + "\n\n".join(turns)


def analyze_feedback(text, duration, avg_logprob):
    words = text.lower().split()
    filler_count = sum(1 for word in words if word in FILLER_WORDS)
    word_count = len(words)
    wpm = int((word_count / max(duration, 0.5)) * 60)
    clarity_score = int(math.exp(max(avg_logprob, -5.0)) * 100)

    feedback = {
        "filler_words_count": filler_count,
        "word_count": word_count,
        "wpm": wpm,
        "clarity_score": clarity_score,
        "suggestions": [],
    }

    if filler_count > 3:
        feedback["suggestions"].append("Try to use fewer filler words.")
    if word_count < 10:
        feedback["suggestions"].append("Try to elaborate more.")
    if wpm > 170:
        feedback["suggestions"].append("Slow down, you're speaking fast.")
    elif wpm < 90 and word_count > 5:
        feedback["suggestions"].append("Increase your pace for better flow.")
    if clarity_score < 70:
        feedback["suggestions"].append("Work on your articulation.")
    return feedback


def is_garbage_transcription(text):
    if not text:
        return True
    base_text = re.sub(r"[.,!?]", "", text.lower())
    words = base_text.split()

    if len(words) > 3:
        counts = Counter(words)
        if counts.most_common(1)[0][1] / len(words) >= 0.5:
            return True

    clean_text = re.sub(r"[^a-zA-Z0-9\s.,!?']", "", text)
    if not clean_text.strip() or len(clean_text) / len(text) < 0.6:
        return True
    if len(words) < 3:
        return True
    return False


def get_difficulty_label(answer_depth, history_len):
    if history_len < 4:
        return ""
    if answer_depth < 40:
        return " (the candidate seems to be struggling — consider a simpler follow-up)"
    if answer_depth > 80:
        return " (the candidate answered well — ask a more challenging follow-up)"
    return ""
