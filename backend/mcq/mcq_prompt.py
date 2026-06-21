"""RAG-based MCQ generation: retrieve -> build prompt -> LLM -> validate -> retry."""

import json
import re
import asyncio
from log_utils import logger
from llm_client import ask_llm
from rag.retriever import retrieve

MCQ_PROMPT_TEMPLATE = """You are an MCQ generator. Create one multiple-choice question that tests understanding of a concept from the provided context.

Context:
{context}

Subject: {subject}
Topic: {topic}
Difficulty level (1-5): {difficulty}
{instruction}

Rules:
- Base the question on a real concept from the context (not on metadata about the book itself).
- Do NOT ask about "what this book covers", "which operating system is discussed", "what chapter introduces X", or similar book-metadata questions.
- Ask about the concept itself: e.g. "What is virtual memory?" not "Which book covers virtual memory?".

Return ONLY a valid JSON object with exactly these fields (no markdown, no explanation wrapper):
{{
  "question": "string — the question text",
  "options": ["A", "B", "C", "D"],
  "correct_index": 0-3,
  "explanation": "string — why this answer is correct"
}}
"""

DIFFICULTY_INSTRUCTIONS = {
    1: "Instruction: Basic recall — single definition or fact. One obviously wrong distractor. Example: 'What is X?', where one option is clearly nonsense.",
    2: "Instruction: Straightforward understanding — requires knowing one concept. Distractors are plausible but wrong. Example: 'What does X do?' where the wrong options describe related but different things.",
    3: "Instruction: Applied understanding — apply one concept to a realistic scenario, or connect two concepts. All distractors must be plausible. Example: 'Given scenario S, which approach works?' where every option is a real technique but only one fits.",
    4: "Instruction: Complex reasoning — multi-step analysis, a specific edge case, or a trap for a common misconception. Distractors must target specific mistakes a learner would make. Example: 'If constraint X changes, what happens?' or 'Which case does this not handle?'",
    5: "Instruction: Expert-level — combine concepts from different areas of the subject, reason about trade-offs, or identify the flaw in a plausible-but-wrong approach. Distractors must be subtle and trap overconfident learners. Example: 'Which optimization introduces a correctness bug?' or 'Under conditions A and B, which design fails?'",
}

VALID_TOPICS = {"arrays", "linked_lists", "trees", "graphs", "dp", "sorting_searching", "recursion",
                "os", "dbms", "cn", "oop",
                "quant_arithmetic", "quant_algebra", "logical_reasoning", "data_interpretation",
                "reading_comprehension", "grammar", "vocabulary", "sentence_correction"}


_TOPIC_QUERIES = {
    "verbal": "define vocabulary grammar reading comprehension passage",
    "aptitude": "solve calculate arithmetic reasoning problem example",
    "cs_fundamentals": "operating system process scheduling memory management database query networking protocol",
    "dsa": "algorithm data structure time complexity example implementation",
    "system_design": "design scalable system architecture trade-offs example",
}


def _build_topic_query(subject: str, topic: str | None) -> str:
    if topic:
        return f"explain the concept of {topic} in {subject} with an example"
    base = _TOPIC_QUERIES.get(subject, f"{subject} concepts explained with examples")
    return base


def _difficulty_instruction(difficulty: int) -> str:
    return DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS[3])


def _validate_question(data: dict) -> str | None:
    """Validate parsed JSON. Returns None if valid, error string otherwise."""
    if not isinstance(data, dict):
        return "Response is not a JSON object"
    if "question" not in data or not isinstance(data.get("question"), str) or not data["question"].strip():
        return "Missing or empty 'question' field"
    options = data.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return f"Expected exactly 4 'options', got {len(options) if isinstance(options, list) else 'not a list'}"
    for i, opt in enumerate(options):
        if not isinstance(opt, str) or not opt.strip():
            return f"Option {i} is empty or not a string"
    seen = set()
    for opt in options:
        key = opt.strip().lower()
        if key in seen:
            return f"Duplicate option text: '{opt.strip()}'"
        seen.add(key)
    ci = data.get("correct_index")
    if not isinstance(ci, int) or ci < 0 or ci > 3:
        return f"'correct_index' must be 0-3, got {ci}"
    if "explanation" not in data or not isinstance(data.get("explanation"), str) or not data["explanation"].strip():
        return "Missing or empty 'explanation' field"
    return None


def _parse_json(raw: str) -> dict | None:
    """Extract JSON from LLM response (handles markdown fences)."""
    # Try direct parse first
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... } block
    m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


_NON_SUBSTANTIVE_SECTIONS = {
    "Content of This Book", "Bibliographical Notes", "Exercises", "Bibliographical Notes ",
    "Bibliographical Notes", "Summary", "Key Terms", "Practice Exercises",
    "We have also added more practice exercises",
}

_NON_SUBSTANTIVE_OPENINGS = (
    "this book uses examples", "this book covers", "this book is organized",
    "now that you understand", "we can now integrate", "in this chapter we",
    "concepts described in the earlier chapters", "the concepts described in the earlier",
    "in this chapter, we", "we have also added", "this chapter presents",
    "content of this book",
)


def _is_non_substantive(doc: str, meta: dict) -> bool:
    section = meta.get("section", "")
    if section in _NON_SUBSTANTIVE_SECTIONS:
        return True
    opening = doc.strip().lower()[:100]
    for pat in _NON_SUBSTANTIVE_OPENINGS:
        if pat in opening:
            return True
    return False


async def generate_mcq(subject: str, topic: str | None = None, difficulty: int = 3) -> dict | None:
    """Generate one MCQ question. Returns the question dict or None on failure."""
    query = _build_topic_query(subject, topic)
    conditions = [{"subject": subject}, {"section": {"$ne": "front_matter"}}]
    if topic:
        conditions.append({"topic": topic})
    where_filter = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    try:
        results = retrieve(query, top_k=15, where_filter=where_filter)
    except Exception:
        logger.exception("MCQ retrieval failed for %s/%s", subject, topic)
        return None

    if not results and topic:
        # Topic filter returned nothing; fall back to subject-only
        logger.warning("MCQ: no results for %s/%s, retrying without topic filter", subject, topic)
        try:
            results = retrieve(query, top_k=15, where_filter={"$and": [{"subject": subject}, {"section": {"$ne": "front_matter"}}]})
        except Exception:
            return None

    if not results:
        logger.warning("MCQ: no results retrieved for %s/%s", subject, topic)
        return None

    # Filter out non-substantive chunks (introductory/metadata sections)
    filtered = [(doc, meta, score) for doc, meta, score in results if not _is_non_substantive(doc, meta)]
    if not filtered:
        logger.warning("MCQ: all results filtered as non-substantive for %s/%s, using original", subject, topic)
        filtered = results

    # Build context from top chunks — scale with difficulty so higher levels
    # have enough breadth to combine concepts or reason about edge cases.
    if difficulty >= 4:
        max_chunks = 12
        char_budget = 2000
    elif difficulty >= 3:
        max_chunks = 8
        char_budget = 1200
    else:
        max_chunks = 5
        char_budget = 600
    context_parts = []
    for doc, meta, score in filtered[:max_chunks]:
        doc_stripped = doc.strip()
        if doc_stripped.startswith("### Prerequisites") or doc_stripped.startswith("## Prerequisites"):
            continue
        avail = char_budget - sum(len(p) for p in context_parts)
        if avail <= 0:
            break
        source = meta.get("source", "?")
        tag = f"topic={meta.get('topic','?')}" if meta.get("topic") else f"p.{meta.get('page','?')}"
        snippet = doc[:avail]
        context_parts.append(f"[{source} {tag}] {snippet}")
    context = "\n\n".join(context_parts) if context_parts else "(no relevant context)"

    prompt = MCQ_PROMPT_TEMPLATE.format(
        context=context,
        subject=subject,
        topic=topic or "general",
        difficulty=difficulty,
        instruction=_difficulty_instruction(difficulty),
    )

    # First attempt
    raw = await ask_llm(prompt, stop_tokens=[], temperature=0.3, top_k=40, repeat_penalty=1.1)
    parsed = _parse_json(raw)
    if parsed:
        err = _validate_question(parsed)
        if err is None:
            parsed["subject"] = subject
            parsed["topic"] = topic
            parsed["difficulty"] = difficulty
            parsed["source_chunks"] = [
                {"source": m.get("source", "?"), "page": m.get("page", "?")}
                for _, m, _ in results[:3]
            ]
            return parsed
        logger.warning("MCQ validation failed (attempt 1): %s", err)
    else:
        logger.warning("MCQ JSON parse failed (attempt 1)")

    # Retry with stricter instruction
    retry_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no backticks, no extra text."
    raw = await ask_llm(retry_prompt, stop_tokens=[], temperature=0.2, top_k=40, repeat_penalty=1.2)
    parsed = _parse_json(raw)
    if parsed:
        err = _validate_question(parsed)
        if err is None:
            parsed["subject"] = subject
            parsed["topic"] = topic
            parsed["difficulty"] = difficulty
            parsed["source_chunks"] = [
                {"source": m.get("source", "?"), "page": m.get("page", "?")}
                for _, m, _ in results[:3]
            ]
            return parsed
        logger.warning("MCQ validation failed (attempt 2): %s", err)

    logger.error("MCQ generation failed for %s/%s after 2 attempts", subject, topic)
    return None
