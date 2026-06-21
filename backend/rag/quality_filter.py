import re
import hashlib


def deduplicate(chunks, metadatas=None):
    seen = set()
    unique_chunks = []
    unique_metas = []
    for i, c in enumerate(chunks):
        sig = hashlib.md5(c.strip().lower().encode()).hexdigest()
        if sig not in seen:
            seen.add(sig)
            unique_chunks.append(c)
            if metadatas:
                unique_metas.append(metadatas[i])
    return unique_chunks, (unique_metas if metadatas else None)


def is_junk(chunk):
    chunk_lower = chunk.strip().lower()
    if len(chunk.split()) < 8:
        return True
    junk_patterns = [
        r"copyright\s+©",
        r"all rights reserved",
        r"page\s+intentionally\s+left\s+blank",
        r"www\.\w+\.\w+",
        r"^table\s+of\s+contents",
        r"^index$",
        r"\bpreface\b",
        r"\babout\s+the\s+(author|book|edition)\b",
        r"\b(?:this\s+)?book\s+(?:is\s+)?intended\s+for\b",
        r"\b(?:we|i)\s+(?:have\s+)?(?:written|organized|designed)\s+this\s+book\b",
        r"\b(?:acknowledgments?|acknowledgements?)\b",
        r"\bdedication\b",
        r"^\s*contents\s*$",
    ]
    for pat in junk_patterns:
        if re.search(pat, chunk_lower):
            return True
    return False


def filter_junk(chunks, metadatas=None):
    if metadatas:
        result = [(c, m) for c, m in zip(chunks, metadatas) if not is_junk(c)]
        return [r[0] for r in result], [r[1] for r in result]
    return [c for c in chunks if not is_junk(c)], None


def quality_filter(chunks, metadatas=None):
    chunks, metadatas = filter_junk(chunks, metadatas)
    chunks, metadatas = deduplicate(chunks, metadatas)
    return chunks, metadatas
