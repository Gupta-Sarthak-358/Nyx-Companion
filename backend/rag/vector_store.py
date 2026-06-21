import os
import chromadb
from chromadb.config import Settings

from config import CHROMA_DB_DIR

DB_DIR = CHROMA_DB_DIR
COLLECTION_NAME = "knowledge_base"

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(anonymized_telemetry=False))
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME in existing:
            _collection = client.get_collection(COLLECTION_NAME)
        else:
            _collection = client.create_collection(COLLECTION_NAME)
    return _collection


def add_chunks(chunks, embeddings, source, metadatas=None, subject=None):
    collection = get_collection()
    ids = [f"{source}_{i}" for i in range(len(chunks))]
    metas = []
    for i in range(len(chunks)):
        m = {"source": source}
        if subject:
            m["subject"] = subject
        if metadatas and i < len(metadatas):
            m.update(metadatas[i])
        metas.append(m)
    collection.add(ids=ids, documents=chunks, embeddings=embeddings.tolist(), metadatas=metas)
    return len(chunks)


def search(query_embedding, top_k=5, where=None):
    collection = get_collection()
    kwargs = {"query_embeddings": [query_embedding.tolist()], "n_results": top_k}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)
    return results


def count_documents():
    collection = get_collection()
    return collection.count()


def list_sources():
    collection = get_collection()
    results = collection.get(include=["metadatas"])
    seen = set()
    sources = []
    for m in (results.get("metadatas") or []):
        s = m.get("source", "unknown")
        if s not in seen:
            seen.add(s)
            sources.append(s)
    return sources


def delete_source(source):
    collection = get_collection()
    results = collection.get(where={"source": source}, include=[])
    if results["ids"]:
        collection.delete(ids=results["ids"])
    return len(results["ids"])
