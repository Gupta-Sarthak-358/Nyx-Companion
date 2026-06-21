import os
import sys
import json
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from rag.chunker import chunk_pdf, chunk_markdown
from rag.embeddings import embed_texts
from rag.vector_store import add_chunks, count_documents, list_sources
from rag.quality_filter import quality_filter
from config import BOOKS_DIR, PROCESSED_DIR
from log_utils import logger
from mcq.taxonomy import is_valid_subject, SUBJECTS

SUBJECT_FOLDERS = set(SUBJECTS.keys())


def _chunk_file(path, subject=None):
    """Dispatch to chunk_pdf or chunk_markdown based on extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        return chunk_markdown(path, subject=subject)
    return chunk_pdf(path, subject=subject)


def ingest_file(file_path, subject=None, progress_callback=None):
    fname = os.path.basename(file_path)
    logger.info("Ingesting: %s (subject=%s)", fname, subject or "none")
    if progress_callback:
        progress_callback(fname, 0, 4, "Chunking...")

    chunks, metadatas = _chunk_file(file_path, subject=subject)
    logger.info("  Extracted %d raw chunks", len(chunks))
    if progress_callback:
        progress_callback(fname, 1, 4, "Filtering...")

    chunks, metadatas = quality_filter(chunks, metadatas)
    logger.info("  After quality filter: %d chunks", len(chunks))

    if not chunks:
        logger.warning("  Skipping %s — no usable content", fname)
        if progress_callback:
            progress_callback(fname, 4, 4, "Skipped (no content)")
        return
    if progress_callback:
        progress_callback(fname, 2, 4, "Embedding...")

    embeddings = embed_texts(chunks)
    logger.info("  Generated %d embeddings", len(embeddings))
    if progress_callback:
        progress_callback(fname, 3, 4, "Storing...")

    count = add_chunks(chunks, embeddings, source=fname, metadatas=metadatas, subject=subject)
    logger.info("  Stored %d chunks in ChromaDB", count)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    processed_flag = os.path.join(PROCESSED_DIR, fname + ".done")
    with open(processed_flag, "w") as f:
        json.dump({"source": fname, "chunks": len(chunks), "timestamp": time.time()}, f)

    logger.info("Done — %s", fname)
    if progress_callback:
        progress_callback(fname, 4, 4, "Done")


def _get_subject_for_path(path):
    """Infer subject from the parent folder name. Returns None for flat BOOKS_DIR."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if is_valid_subject(parent):
        return parent
    return None


_DOC_EXTENSIONS = {".pdf", ".md"}


def _find_docs(directory):
    """Find all .pdf and .md files in a directory (recursive)."""
    docs = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in _DOC_EXTENSIONS:
                rel = os.path.relpath(os.path.join(root, f), directory)
                docs.append(rel)
    return sorted(docs)


def _find_flat_docs(directory):
    """Find .pdf and .md files directly in a directory (non-recursive)."""
    return sorted(
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and os.path.splitext(f)[1].lower() in _DOC_EXTENSIONS
    )


def ingest_all(progress_callback=None):
    if not os.path.isdir(BOOKS_DIR):
        logger.error("Books directory not found: %s", BOOKS_DIR)
        return

    found_any = False

    # Walk subdirectories for subject-tagged documents
    for entry in sorted(os.listdir(BOOKS_DIR)):
        subpath = os.path.join(BOOKS_DIR, entry)
        if os.path.isdir(subpath) and entry in SUBJECT_FOLDERS:
            docs = _find_docs(subpath)
            if not docs:
                continue
            found_any = True
            logger.info("Subject folder '%s': %d file(s)", entry, len(docs))
            for idx, doc in enumerate(docs, 1):
                path = os.path.join(subpath, doc)
                if progress_callback:
                    progress_callback(doc, 0, 4, f"Subject: {entry} — Starting...", current_file=idx, total_files=len(docs))
                ingest_file(path, subject=entry, progress_callback=progress_callback)

    # Also handle flat documents in BOOKS_DIR root (no subject, non-recursive)
    flat_docs = _find_flat_docs(BOOKS_DIR)
    if flat_docs:
        found_any = True
        logger.info("Flat docs (no subject): %d file(s)", len(flat_docs))
        for idx, doc in enumerate(flat_docs, 1):
            path = os.path.join(BOOKS_DIR, doc)
            ingest_file(path, subject=None, progress_callback=progress_callback)

    if not found_any:
        logger.warning("No documents found in %s or its subject subfolders", BOOKS_DIR)
        return

    total = count_documents()
    logger.info("Total documents in vector store: %d", total)
    logger.info("Sources: %s", list_sources())


if __name__ == "__main__":
    ingest_all()
