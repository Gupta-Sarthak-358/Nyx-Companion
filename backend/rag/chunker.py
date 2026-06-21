import os
import re
import bisect
from pypdf import PdfReader

TOKEN_CHUNK_SIZE = 400
TOKEN_OVERLAP = 64

SECTION_PATTERNS = [
    re.compile(r"^(?:Chapter|CHAPTER|Ch\.)\s+\d+[\.:]?\s*(.*)$", re.MULTILINE),
    re.compile(r"^\d+\.\d+\s+[A-Z].*$", re.MULTILINE),
    re.compile(r"^##\s+.+$", re.MULTILINE),
    re.compile(r"^[A-Z][A-Z\s]{3,50}$", re.MULTILINE),
]

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
    return _tokenizer


def extract_text_from_pdf(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            pages.append((i + 1, page_text))
    return pages


def clean_text(text):
    text = re.sub(r"Copyright ©?\s*\d{4}.*?\.", "", text)
    text = re.sub(r"All\s+rights\s+reserved\.?", "", text, flags=re.I)
    text = re.sub(r"Page\s+intentionally\s+left\s+blank", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_page_boundaries(pages):
    boundaries = []
    offset = 0
    for page_num, text in pages:
        boundaries.append((offset, page_num))
        offset += len(text)
    return boundaries


def _find_page(char_pos, boundaries):
    offsets = [b[0] for b in boundaries]
    i = bisect.bisect_right(offsets, char_pos) - 1
    return boundaries[i][1] if i >= 0 else 1


def _find_section_headers(text):
    lines = text.split("\n")
    headers = []
    char_offset = 0
    for _, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            char_offset += len(line) + 1
            continue
        matched = False
        for pat in SECTION_PATTERNS:
            m = pat.match(stripped)
            if m:
                header_text = m.group(1) if m.lastindex else stripped
                headers.append((char_offset, header_text))
                matched = True
                break
        if not matched:
            if len(stripped.split()) <= 6 and len(stripped) <= 80 and not stripped.endswith("."):
                if stripped[0].isupper() and any(c.islower() for c in stripped[1:]):
                    headers.append((char_offset, stripped))
        char_offset += len(line) + 1
    return headers


def _find_section(char_pos, headers):
    section = None
    for offset, title in headers:
        if offset <= char_pos:
            section = title
        else:
            break
    return section


def _chunk_segment(segment_text, char_base, chunk_size, overlap):
    """Chunk a single section segment (never crosses section boundaries)."""
    tokenizer = _get_tokenizer()
    encoding = tokenizer(segment_text, return_offsets_mapping=True, add_special_tokens=False, truncation=False)
    token_ids = encoding["input_ids"]
    offsets = encoding["offset_mapping"]
    if not token_ids:
        return [], []
    chunks = []
    chunk_offsets = []
    for i in range(0, len(token_ids), chunk_size - overlap):
        start = i
        end = min(i + chunk_size, len(token_ids))
        ct = tokenizer.decode(token_ids[start:end], skip_special_tokens=True)
        if len(ct.strip()) < 20:
            continue
        char_start = char_base + offsets[start][0]
        char_end = char_base + offsets[end - 1][1]
        chunks.append(ct)
        chunk_offsets.append((char_start, char_end))
    return chunks, chunk_offsets


def chunk_text(text, chunk_size=TOKEN_CHUNK_SIZE, overlap=TOKEN_OVERLAP):
    section_headers = _find_section_headers(text)
    if section_headers:
        segments = []
        prev_end = 0
        for offset, _title in section_headers:
            if offset > prev_end:
                segments.append(text[prev_end:offset])
            prev_end = offset
        segments.append(text[prev_end:])
    else:
        segments = [text]

    all_chunks = []
    all_offsets = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        char_base = text.find(seg)
        if char_base < 0:
            char_base = 0
        c, o = _chunk_segment(seg, char_base, chunk_size, overlap)
        all_chunks.extend(c)
        all_offsets.extend(o)
    return all_chunks, all_offsets


def _find_first_content_header(headers: list) -> int | None:
    """Find the char offset of the first 'real' content header (Chapter, numbered section).
    Returns None if no content header is found."""
    content_patterns = [
        re.compile(r"^(?:Chapter|CHAPTER|Ch\.)\s+\d+"),
        re.compile(r"^\d+\.\d+\s+[A-Z]"),
    ]
    for offset, title in headers:
        for pat in content_patterns:
            if pat.match(title):
                return offset
    return None


_FRONT_MATTER_PAGE_CUTOFF = 10


def _is_front_matter(char_start: int, page: int, first_content_offset: int | None) -> bool:
    """Determine if a chunk is front matter (before first chapter)."""
    if first_content_offset is not None and char_start < first_content_offset:
        return True
    if first_content_offset is None and page <= _FRONT_MATTER_PAGE_CUTOFF:
        return True
    return False


def chunk_pdf(path, chunk_size=TOKEN_CHUNK_SIZE, overlap=TOKEN_OVERLAP, subject=None):
    pages = extract_text_from_pdf(path)
    fname = os.path.basename(path)

    topic = None
    if subject:
        from mcq.taxonomy import pdf_filename_to_topic
        topic = pdf_filename_to_topic(fname, subject)

    cleaned_pages = [(pn, clean_text(text)) for pn, text in pages]
    page_boundaries = _build_page_boundaries(cleaned_pages)

    full_text = "\n".join(text for _, text in cleaned_pages)
    full_text = clean_text(full_text)

    section_headers = _find_section_headers(full_text)
    first_content_offset = _find_first_content_header(section_headers)

    chunks, chunk_offsets = chunk_text(full_text, chunk_size, overlap)

    all_chunks = []
    all_metas = []

    for seg_text, (char_start, char_end) in zip(chunks, chunk_offsets):
        pn = _find_page(char_start, page_boundaries)
        section_title = _find_section(char_start, section_headers)

        if _is_front_matter(char_start, pn, first_content_offset):
            section_title = "front_matter"

        all_chunks.append(seg_text)
        meta = {
            "source": fname,
            "page": pn,
        }
        if subject:
            meta["subject"] = subject
        if topic:
            meta["topic"] = topic
        if section_title:
            meta["section"] = section_title
        all_metas.append(meta)

    return all_chunks, all_metas


def _filename_to_topic(fname: str) -> str | None:
    """Exact-match filename stem against all known topics."""
    stem = os.path.splitext(fname)[0].lower().replace("-", "_").replace(" ", "_")
    try:
        from mcq.taxonomy import SUBJECTS
        all_topics = set()
        for topics in SUBJECTS.values():
            all_topics.update(topics)
        if stem in all_topics:
            return stem
    except ImportError:
        pass
    return None


def _is_in_code_block(lines: list[str], line_idx: int) -> bool:
    """Check if line_idx is inside a fenced code block."""
    count = 0
    for i in range(line_idx + 1):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            count += 1
    return count % 2 == 1


def chunk_markdown(path: str, chunk_size: int = TOKEN_CHUNK_SIZE, overlap: int = TOKEN_OVERLAP, subject: str | None = None) -> tuple[list[str], list[dict]]:
    """Chunk a markdown file on section headers, never splitting code blocks or tables."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    fname = os.path.basename(path)
    topic = _filename_to_topic(fname)
    tokenizer = _get_tokenizer()

    # Find header lines (## or ###)
    header_re = re.compile(r"^(#{2,3})\s+(.*)")
    header_indices = []
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m and not _is_in_code_block(lines, i):
            header_indices.append(i)

    if not header_indices:
        header_indices = [0]

    # Split into sections at header boundaries
    sections = []
    for idx, hdr_idx in enumerate(header_indices):
        start = hdr_idx
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        header_text = header_re.match(lines[hdr_idx]).group(2) if header_re.match(lines[hdr_idx]) else ""
        text = "".join(lines[start:end])
        sections.append((start, end, header_text.strip(), text))

    all_chunks = []
    all_metas = []

    for sec_start, sec_end, sec_title, sec_text in sections:
        sec_text = sec_text.strip()
        if not sec_text:
            continue

        section_lines = lines[sec_start:sec_end]
        tokens = tokenizer.encode(sec_text, add_special_tokens=False)
        if not tokens:
            continue

        # Build atomic groups: contiguous line ranges that must stay together
        # (code blocks, tables). Everything else can be split freely on line boundaries.
        atomic_groups = _build_atomic_groups(section_lines)

        # Walk lines and group into chunks respecting token budget
        chunk_start_line = 0
        while chunk_start_line < len(section_lines):
            chunk_end_line = chunk_start_line

            while chunk_end_line < len(section_lines):
                # Find group end: whole atomic group, or single line
                group_end = chunk_end_line + 1  # default: advance by one line
                for a_start, a_end in atomic_groups:
                    if a_start <= chunk_end_line < a_end:
                        group_end = a_end  # whole atomic group must stay together
                        break

                candidate_text = _text_for_lines(section_lines, chunk_start_line, group_end)
                candidate_tokens = tokenizer.encode(candidate_text, add_special_tokens=False)

                if len(candidate_tokens) <= chunk_size:
                    chunk_end_line = group_end
                    tok_count = len(candidate_tokens)
                elif chunk_end_line == chunk_start_line:
                    # Single atomic group exceeds chunk_size — include it anyway
                    chunk_end_line = group_end
                    tok_count = len(candidate_tokens)
                    break
                else:
                    break

            chunk_text = _text_for_lines(section_lines, chunk_start_line, chunk_end_line)
            if not chunk_text:
                chunk_start_line = chunk_end_line
                continue

            all_chunks.append(chunk_text)
            meta = {"source": fname}
            if subject:
                meta["subject"] = subject
            if topic:
                meta["topic"] = topic
            if sec_title:
                meta["section"] = sec_title
            all_metas.append(meta)

            # Handle overlap (next chunk starts within current chunk, token-budgeted)
            if chunk_end_line >= len(section_lines):
                break

            next_start = chunk_end_line
            if overlap > 0:
                for oi in range(chunk_end_line - 1, chunk_start_line, -1):
                    back_text = _text_for_lines(section_lines, oi, chunk_end_line)
                    bt = tokenizer.encode(back_text, add_special_tokens=False)
                    if len(bt) <= overlap:
                        next_start = oi
                        break
            chunk_start_line = max(next_start, chunk_start_line + 1)

            if chunk_start_line >= len(section_lines):
                break

    return all_chunks, all_metas


def _text_for_lines(section_lines: list[str], start: int, end: int) -> str:
    """Join section lines from start to end, stripping trailing whitespace."""
    return "".join(section_lines[start:end]).strip()


def _build_atomic_groups(lines: list[str]) -> list[tuple[int, int]]:
    """Find contiguous line ranges that must stay together (code blocks, tables).
    Returns list of (start, end) tuples."""
    groups = []
    in_code = False
    in_table = False
    table_start = -1
    code_start = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Code block markers
        if stripped.startswith("```"):
            if in_code:
                groups.append((code_start, i + 1))
                in_code = False
                code_start = -1
            else:
                in_code = True
                code_start = i
            continue

        # Table detection
        if not in_code:
            if stripped.startswith("|") and not in_table:
                in_table = True
                table_start = i
            elif in_table and not stripped.startswith("|"):
                groups.append((table_start, i))
                in_table = False

    # Close any open groups
    if in_code and code_start >= 0:
        groups.append((code_start, len(lines)))
    if in_table and table_start >= 0:
        groups.append((table_start, len(lines)))

    return groups
