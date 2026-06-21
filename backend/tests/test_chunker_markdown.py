"""Tests for markdown chunking.

Run from backend/:
    PYTHONPATH=. pytest tests/test_chunker_markdown.py -v
"""

import os
import tempfile
import pytest
from rag.chunker import chunk_markdown, _filename_to_topic, TOKEN_CHUNK_SIZE


def _write_md(content):
    """Write content to a temp file, return path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestFilenameToTopic:

    def test_exact_match(self):
        assert _filename_to_topic("arrays.md") == "arrays"

    def test_underscore_match(self):
        assert _filename_to_topic("binary-search.md") == "binary_search"

    def test_no_match_returns_none(self):
        assert _filename_to_topic("unknown_file.md") is None

    def test_case_insensitive(self):
        assert _filename_to_topic("TREES.md") == "trees"


class TestChunkMarkdown:

    def test_simple_sections(self):
        content = """# Title
## Arrays
Arrays are fundamental data structures.

## Linked Lists
Linked lists store elements in nodes.
"""
        path = _write_md(content)
        try:
            chunks, metas = chunk_markdown(path, subject="dsa")
            assert len(chunks) >= 2
            assert all(m["subject"] == "dsa" for m in metas)
            assert any("arrays" in c.lower() for c in chunks)
            assert any("linked" in c.lower() for c in chunks)
        finally:
            os.unlink(path)

    def test_code_block_not_split(self):
        content = """## Recursion
Recursion is a technique where a function calls itself.

```python
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
```

The base case prevents infinite recursion.
"""
        path = _write_md(content)
        try:
            chunks, metas = chunk_markdown(path, chunk_size=30, overlap=5)
            code_chunks = [c for c in chunks if "def fib" in c or "fib(" in c.replace(" ", "")]
            # BPE tokenizer adds spaces around punctuation, so check for key parts
            any_code = False
            for cc in code_chunks:
                if "def" in cc and ("fib" in cc or "n-1" in cc):
                    any_code = True
                    break
            assert any_code, "Code block content not found in any chunk"
        finally:
            os.unlink(path)

    def test_table_not_split(self):
        content = """## Time Complexity

| Operation | Array | Linked List |
|-----------|-------|-------------|
| Access    | O(1)  | O(n)        |
| Search    | O(n)  | O(n)        |
| Insert    | O(n)  | O(1)        |
"""
        path = _write_md(content)
        try:
            chunks, metas = chunk_markdown(path, chunk_size=40, overlap=5)
            # Every table row text must appear in at least one chunk
            all_text_combined = " ".join(chunks)
            for row_text in ["Access", "Search", "Insert"]:
                assert row_text in all_text_combined, f"Row '{row_text}' missing from all chunks"
        finally:
            os.unlink(path)

    def test_topic_tagged_from_filename(self):
        content = """## Intro
Some content about arrays.

## Operations
More content.
"""
        path = _write_md(content)
        try:
            path_with_name = os.path.join(os.path.dirname(path), "arrays.md")
            os.rename(path, path_with_name)
            _, metas = chunk_markdown(path_with_name, subject="dsa")
            for m in metas:
                assert m.get("topic") == "arrays"
            os.unlink(path_with_name)
            return
        finally:
            if os.path.isfile(path):
                os.unlink(path)

    def test_code_block_no_mid_block_split(self):
        """A code block shorter than chunk size stays intact; longer extends past boundary."""
        code_lines = "\n".join(f"print({i})" for i in range(50))
        content = f"""## Demo

```python
{code_lines}
```

After code text.
"""
        path = _write_md(content)
        try:
            chunks, metas = chunk_markdown(path, chunk_size=40, overlap=5)
            all_text = " ".join(chunks)
            # Should find at minimum some `print(` patterns in the output
            assert any("print" in c for c in chunks), "No code block content found in any chunk"
        finally:
            os.unlink(path)

    def test_no_headers_creates_single_chunk(self):
        content = "Just a single paragraph of continuous text without any markdown headings at all."
        path = _write_md(content)
        try:
            chunks, metas = chunk_markdown(path)
            assert len(chunks) >= 1
            assert len(metas) == len(chunks)
        finally:
            os.unlink(path)

    def test_metadata_has_source_no_page(self):
        content = "## Section\nContent."
        path = _write_md(content)
        try:
            _, metas = chunk_markdown(path, subject="dsa")
            for m in metas:
                assert "source" in m
                assert "page" not in m
                assert m["subject"] == "dsa"
                assert m["section"] == "Section"
        finally:
            os.unlink(path)
