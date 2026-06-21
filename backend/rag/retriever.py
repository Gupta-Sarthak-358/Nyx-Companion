from .embeddings import embed_query
from .vector_store import search
from .reranker import rerank

FETCH_K = 20


def retrieve(query, top_k=5, where_filter=None):
    query_emb = embed_query(query)
    results = search(query_emb, top_k=FETCH_K, where=where_filter)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    scores = results.get("distances", [[]])[0]
    candidates = list(zip(documents, metadatas, scores))
    return rerank(query, candidates, top_k=top_k)


def retrieve_raw(query, top_k=5, where_filter=None):
    query_emb = embed_query(query)
    results = search(query_emb, top_k=top_k, where=where_filter)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    scores = results.get("distances", [[]])[0]
    return list(zip(documents, metadatas, scores))


def format_context(results):
    lines = []
    for doc, meta, score in results:
        source = meta.get("source", "unknown")
        page = meta.get("page")
        section = meta.get("section")
        parts = [source]
        if section:
            parts.append(section)
        if page:
            parts.append(f"p.{page}")
        header = f"[{' — '.join(parts)}] (score: {score:.3f})"
        lines.append(header)
        lines.append(doc)
        lines.append("")
    return "\n".join(lines).strip()
