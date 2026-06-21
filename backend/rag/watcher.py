"""
Standalone directory watcher for auto-ingesting PDFs dropped into BOOKS_DIR.

Not wired into the startup sequence by default. Run manually:
    PYTHONPATH=. python -m rag.watcher

Requires: pip install watchdog
"""

import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pypdf.errors import PdfReadError

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from rag.ingest import ingest_pdf
from config import BOOKS_DIR

STABILITY_POLL_INTERVAL = 0.5
STABILITY_CHECKS = 3


def _wait_for_stable_size(path, timeout=30):
    """Wait until the file size has remained unchanged for N consecutive polls."""
    prev_size = -1
    stable_count = 0
    elapsed = 0.0
    while elapsed < timeout:
        cur = os.path.getsize(path)
        if cur == prev_size and cur > 0:
            stable_count += 1
            if stable_count >= STABILITY_CHECKS:
                return True
        else:
            stable_count = 0
        prev_size = cur
        time.sleep(STABILITY_POLL_INTERVAL)
        elapsed += STABILITY_POLL_INTERVAL
    return False


class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        path = event.src_path
        name = os.path.basename(path)
        print(f"\n[Watcher] New PDF detected: {name}")
        if not _wait_for_stable_size(path):
            print(f"[Watcher] Timeout waiting for {name} to finish writing — skipping")
            return
        # Retry PdfReader up to 3 times (covers transient lock / partial write)
        for attempt in range(3):
            try:
                ingest_pdf(path)
                return
            except PdfReadError:
                if attempt < 2:
                    print(f"[Watcher] PdfReadError reading {name} (attempt {attempt+1}/3) — retrying...")
                    time.sleep(1)
                else:
                    print(f"[Watcher] Failed to ingest {name} after 3 attempts — skipping")


def start_watching():
    os.makedirs(BOOKS_DIR, exist_ok=True)
    event_handler = PDFHandler()
    observer = Observer()
    observer.schedule(event_handler, BOOKS_DIR, recursive=False)
    observer.start()
    print(f"[Watcher] Watching {BOOKS_DIR} for new PDFs...")
    print("[Watcher] Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_watching()
