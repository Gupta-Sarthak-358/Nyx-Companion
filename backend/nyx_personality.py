import random
import re

import prompt_loader

MAX_TURNS = 12

_ABUSE_PATTERNS = [
    re.compile(r"\b(bitch|b!tch|biatch)\b", re.I),
    re.compile(r"\b(shut up|stfu|shut up)\b", re.I),
    re.compile(r"\b(fuck|f\*ck|fck|fk)\b", re.I),
    re.compile(r"\b(dumb|stupid|idiot|moron|retard)\b", re.I),
    re.compile(r"\b(whore|slut|hoe)\b", re.I),
    re.compile(r"\b(asshole|a\*hole|a-hole)\b", re.I),
    re.compile(r"\b(dick|cock)\b", re.I),
    re.compile(r"\b(piss off|go to hell|kys)\b", re.I),
]


def _sys_inst():
    return prompt_loader.get("nyx", "system_instruction")


def _reminder():
    return prompt_loader.get("nyx", "reminder")


def _few_shot():
    return prompt_loader.get_dict("nyx", "few_shot")


def _tones():
    return prompt_loader.get_list("nyx", "tones")


def choose_tone(last_tone=None):
    tones = _tones()
    options = [t for t in tones if t != last_tone]
    return random.choice(options or tones)


def trim_turns(turns, max_turns=MAX_TURNS):
    return turns[-max_turns * 2 :]


def is_abusive(text: str) -> bool:
    return any(p.search(text) for p in _ABUSE_PATTERNS)


_SYSTEM_PROMPT_PATTERNS = [
    r"^You are Nyx,?",
    r"^You are (expressive|witty|sharp|a knowledgeable)",
    r"^Before responding,\s*internally decide",
    r"^Avoid repeating sentence structures",
    r"^Do not repeat (the same|previous)",
    r"^If the (user|context)",
    r"^Prioritize interesting",
    r"^Respond as Nyx",
    r"^Instruction:\s*$",
    r"^### Instruction:\s*$",
]


def clean_response(text, user_role="User", ai_role="Nyx"):
    text = re.sub(rf"^{ai_role}:", "", text, flags=re.I).strip()
    text = re.sub(rf"^{user_role}:", "", text, flags=re.I).strip()
    text = re.sub(r"^(Assistant|AI):", "", text, flags=re.I).strip()
    # Strip known system-prompt lines that leak from the model
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if any(re.match(p, stripped, re.I) for p in _SYSTEM_PROMPT_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def response_repeats(response, turns):
    normalized_response = response.strip().lower()
    if not normalized_response:
        return False
    return any(normalized_response == clean_response(turn).lower() for turn in turns)


def apply_anti_repetition(response, turns):
    if response_repeats(response, turns):
        return f"{response} ...okay, that sounded familiar. Let me put it differently."
    return response


def build_history(turns, include_few_shot=True):
    parts = ["### Instruction:", _sys_inst()]
    if include_few_shot:
        parts.append("")
        parts.extend(f"User: {shot['user']}\nNyx: {shot['nyx']}" for shot in _few_shot())
    if turns:
        parts.append("")
        parts.append("\n\n".join(trim_turns(turns)))
    return "\n\n".join(parts).strip()


def build_prompt(turns, user_text, tone, user_role="User", ai_role="Nyx", include_few_shot=True, rag_context=""):
    history = build_history(turns, include_few_shot=include_few_shot)
    rag_block = f"\n\n{rag_context}\n\n" if rag_context else ""

    abuse_instruction = (
        "The user's message contains abusive language. "
        "DO NOT lecture them about respect or engage in meta-conversation. "
        "Briefly acknowledge neutrally, then immediately redirect to the actual topic or ask what they need help with."
        if is_abusive(user_text)
        else ""
    )

    return (
        f"{_reminder()}\n\n"
        f"{history}\n\n"
        f"Instruction:\n"
        f"Respond as Nyx in a {tone} tone. Do not repeat previous phrasing styles.\n"
        f"{abuse_instruction}\n\n"
        f"{rag_block}"
        f"{user_role}: {user_text}\n"
        f"{ai_role}:"
    )
