"""Integration test: ingest a real PDF into a subject folder, verify metadata appears in ChromaDB.

Run from backend/:
    PYTHONPATH=. pytest tests/test_mcq_integration.py -v --timeout=120

Requires: a small PDF at tests/fixtures/sample.pdf
"""

import os
import tempfile
import pytest

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "fixtures", "sample.pdf")
BOOKS_DIR = os.environ.get("BOOKS_DIR", os.path.expanduser("~/RAG_PHASE_1/AI_interview/knowledge/books"))


@pytest.mark.skipif(not os.path.isfile(SAMPLE_PDF), reason="fixture PDF not found")
def test_subject_metadata_persists_in_chromadb():
    """Ingest a small real PDF into knowledge/books/dsa/, then verify subject metadata."""
    import shutil
    from rag.ingest import ingest_file
    from rag.vector_store import get_collection

    target_dir = os.path.join(BOOKS_DIR, "dsa")
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, "sample_test.pdf")
    shutil.copy2(SAMPLE_PDF, dest)

    try:
        ingest_file(dest, subject="dsa")

        collection = get_collection()
        results = collection.get(
            where={"$and": [{"subject": "dsa"}, {"source": "sample_test.pdf"}]},
            include=["metadatas"],
        )
        metadatas = results.get("metadatas", [])
        assert len(metadatas) > 0, "No chunks with subject=dsa and source=sample_test.pdf found"

        for m in metadatas:
            assert m.get("subject") == "dsa", f"Expected subject=dsa, got {m.get('subject')}"
            src = m.get("source", "")
            assert src == "sample_test.pdf", f"Expected source=sample_test.pdf, got {src}"

    finally:
        if os.path.isfile(dest):
            os.unlink(dest)
        try:
            from rag.vector_store import delete_source
            delete_source("sample_test.pdf")
        except Exception:
            pass
