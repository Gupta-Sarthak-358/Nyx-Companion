import re

from log_utils import logger

# Soft limit: if concatenated chunk text exceeds this, we compress
TOKEN_ESTIMATE_FACTOR = 1.3  # rough chars-per-token for English
MAX_CONTEXT_CHARS = 1200  # ~900 tokens, leaving headroom in 4096 ctx


def estimate_tokens(text: str) -> int:
    return int(len(text) / TOKEN_ESTIMATE_FACTOR) + 1


def compress_results(results, max_chars: int = MAX_CONTEXT_CHARS):
    """Compress retrieved chunks to fit within token budget.

    Strategy:
      1. If total fits, return as-is.
      2. Otherwise, keep high-scoring chunks whole, truncate low-scoring ones.
      3. If still over, concatenate into a single summary-style block.
    """
    if not results:
        return results

    total = sum(len(doc) for doc, _, _ in results)
    if total <= max_chars:
        return results

    logger.info(
        "Compressing %d chunks (%d chars -> target %d)",
        len(results), total, max_chars,
    )

    # Sort by score descending
    scored = sorted(results, key=lambda x: x[2], reverse=True)

    # Keep top chunks whole, truncate the rest
    compressed = []
    budget = max_chars
    for doc, meta, score in scored:
        if budget <= 0:
            break
        if len(doc) <= budget:
            compressed.append((doc, meta, score))
            budget -= len(doc)
        else:
            # Truncate with ellipsis, preserving enough for meaning
            truncated = doc[:budget]
            # Try to break at sentence boundary
            m = re.match(r"^.{1,%d}[.!?\n]" % (budget - 1), truncated)
            if m:
                truncated = m.group(0) + " [truncated]"
            else:
                truncated = truncated.rstrip() + " [truncated]"
            compressed.append((truncated, meta, score))
            budget = 0

    if not compressed:
        # Fallback: take top-K that barely fits
        taken = 0
        for doc, meta, score in scored:
            cost = len(doc) + 50  # overhead
            if taken + cost <= max_chars:
                compressed.append((doc, meta, score))
                taken += cost

    logger.info("Compressed %d -> %d chunks, %d chars", len(results), len(compressed), sum(len(d) for d, _, _ in compressed))
    return compressed


def compress_context_text(context: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Compress a pre-formatted context string directly."""
    if len(context) <= max_chars:
        return context

    budget = max_chars
    # Split into sections by source markers, keep most relevant ones
    sections = re.split(r"(---.*?---)", context)
    # Keep intro/prefix and as many sections as fit
    result = []
    for sec in sections:
        if budget <= 0:
            break
        if len(sec) <= budget:
            result.append(sec)
            budget -= len(sec)
        else:
            result.append(sec[:budget] + " [truncated]")
            budget = 0

    return "".join(result)
