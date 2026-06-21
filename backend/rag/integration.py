from .retriever import retrieve, format_context
from .compressor import compress_results, compress_context_text
from prompt_loader import get as get_prompt

RAG_SYSTEM_PROMPT = get_prompt("tutor", "system")

def build_rag_prompt(query, top_k=5, conversation_history=None):
    results = retrieve(query, top_k=top_k)
    results = compress_results(results)
    context = format_context(results)
    context = compress_context_text(context)

    history_block = ""
    if conversation_history:
        entries = []
        for h in conversation_history[-4:]:
            sources = ", ".join(h.get("sources", []))
            entries.append(f"Previous question: {h['q']}  [sources: {sources}]")
        if entries:
            history_block = "\n".join(entries) + "\n\n"

    prompt = f"""{RAG_SYSTEM_PROMPT}

--- CONVERSATION HISTORY ---
{history_block}--- CONTEXT FROM KNOWLEDGE BASE ---
{context}
--- END CONTEXT ---

User question: {query}

Answer based on the context above. If the user refers to something from a previous turn, use both the conversation history and the new context to answer:"""
    return prompt, results
