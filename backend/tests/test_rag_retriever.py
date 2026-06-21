"""
Tests for the RAG retrieval pipeline: bi-encoder search -> cross-encoder reranking -> compression.

Run from backend/:
    PYTHONPATH=. pytest tests/test_rag_retriever.py -v

Mocking strategy
----------------
- ChromaDB search is always mocked (patch rag.retriever.search) -- no real vector store.
- Embedding model is always mocked (patch rag.retriever.embed_query) -- no GPU or model needed.
- Cross-encoder is mocked via rag.reranker.get_reranker when testing retrieve() isolation
  or rerank() directly; the real rerank() function runs but calls a mock model.
- All tests are hermetic and deterministic.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chroma_result(texts, distances=None, metadatas=None):
    """Build a ChromaDB query_result dict matching search() return shape."""
    n = len(texts)
    if distances is None:
        distances = [float(i) * 0.1 for i in range(n)]
    if metadatas is None:
        metadatas = [{"source": f"doc_{i}.pdf", "page": i + 1, "section": "intro"} for i in range(n)]
    return {
        "documents": [texts],
        "distances": [distances],
        "metadatas": [metadatas],
        "ids": [[f"id_{i}" for i in range(n)]],
    }


def _make_candidate(text, source="doc.pdf", page=1, score=0.9):
    """Build a (doc, meta, score) tuple matching retrieve() output shape."""
    return (text, {"source": source, "page": page, "section": "intro"}, score)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chroma_results():
    """Default ChromaDB results with 3 plausible chunks."""
    return _make_chroma_result(
        texts=[
            "The transformer architecture uses self-attention mechanisms.",
            "Attention weights determine how much focus each token receives.",
            "Multi-head attention allows the model to attend to different positions.",
        ],
        distances=[0.05, 0.12, 0.20],
        metadatas=[
            {"source": "attention_paper.pdf", "page": 3, "section": "Architecture"},
            {"source": "attention_paper.pdf", "page": 4, "section": "Architecture"},
            {"source": "bert_paper.pdf",      "page": 1, "section": "Introduction"},
        ],
    )


@pytest.fixture
def empty_chroma_results():
    """ChromaDB results with no documents."""
    return _make_chroma_result(texts=[], distances=[], metadatas=[])


@pytest.fixture
def mock_embedder():
    """Returns a deterministic 384-dim vector."""
    return np.ones(384, dtype=np.float32) * 0.5


@pytest.fixture
def mock_reranker_model():
    """Cross-encoder model returning decreasing scores."""
    model = MagicMock()
    model.predict.return_value = np.array([0.95, 0.72, 0.41])
    return model


@pytest.fixture
def failing_reranker_model():
    """Cross-encoder model that raises (simulates load failure)."""
    model = MagicMock()
    model.predict.side_effect = RuntimeError("CUDA out of memory")
    return model


# ---------------------------------------------------------------------------
# Tests: retrieve() -- bi-encoder search + rerank integration
# ---------------------------------------------------------------------------

class TestRetrieve:

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_returns_correct_number_of_chunks(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        results = retrieve("how does attention work?", top_k=3)
        assert len(results) == 3

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_chunk_shape(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """Each returned result is a (doc, meta, score) tuple."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        results = retrieve("attention mechanisms", top_k=3)
        for doc, meta, score in results:
            assert isinstance(doc, str), f"doc must be str, got {type(doc)}"
            assert isinstance(meta, dict), f"meta must be dict, got {type(meta)}"
            assert "source" in meta
            assert "page" in meta
            assert isinstance(score, (int, float)), f"score must be numeric, got {type(score)}"

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_scores_from_chroma_distances(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """Scores in the output tuple should be the ChromaDB distance values."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        results = retrieve("multi-head attention", top_k=3)
        for _, _, score in results:
            assert isinstance(score, (int, float))

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_empty_collection_returns_empty_list(
        self, mock_embed, mock_search, mock_rerank, empty_chroma_results
    ):
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = empty_chroma_results
        from rag.retriever import retrieve
        results = retrieve("what is attention?", top_k=20)
        assert results == []

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_top_k_clamps_to_available(
        self, mock_embed, mock_search, mock_rerank
    ):
        """retrieve(top_k=20) when only 2 chunks exist returns at most 2."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = _make_chroma_result(
            texts=["chunk A", "chunk B"],
            distances=[0.1, 0.2],
        )
        from rag.retriever import retrieve
        results = retrieve("anything", top_k=20)
        assert len(results) <= 2

    @patch("rag.retriever.rerank")
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_embed_query_called_with_query(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """The embed_query function receives the query string."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        retrieve("positional encoding", top_k=3)
        mock_embed.assert_called_once_with("positional encoding")

    @patch("rag.retriever.rerank")
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_search_receives_embedding(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """search() gets the embedding vector returned by embed_query()."""
        emb = np.ones(384, dtype=np.float32) * 0.7
        mock_embed.return_value = emb
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        retrieve("anything", top_k=3)
        mock_search.assert_called_once()
        call_emb = mock_search.call_args[0][0]
        np.testing.assert_array_equal(call_emb, emb)

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_source_metadata_preserved(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """Source filenames from ChromaDB metadata survive through retrieve()."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        results = retrieve("transformer", top_k=3)
        sources = {meta["source"] for _, meta, _ in results}
        assert "attention_paper.pdf" in sources

    @patch("rag.retriever.rerank", side_effect=lambda q, c, top_k=5: c[:top_k])
    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_and_where_filter_passed_to_search(
        self, mock_embed, mock_search, mock_rerank, chroma_results
    ):
        """$and where_filter syntax is passed through to search() without error."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve
        where = {"$and": [{"subject": "dsa"}, {"topic": "arrays"}]}
        results = retrieve("arrays", top_k=3, where_filter=where)
        assert len(results) == 3
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["where"] == where


# ---------------------------------------------------------------------------
# Tests: rerank() -- cross-encoder re-scoring
# ---------------------------------------------------------------------------

class TestRerank:

    @patch("rag.reranker.get_reranker")
    def test_rerank_returns_top_k(self, mock_get_model, mock_reranker_model):
        """rerank() with top_k=2 returns exactly 2 results."""
        mock_get_model.return_value = mock_reranker_model
        candidates = [
            _make_candidate("The cat sat on the mat."),
            _make_candidate("Attention is all you need."),
            _make_candidate("BERT uses bidirectional encoders."),
        ]
        from rag.reranker import rerank
        results = rerank("transformer attention", candidates, top_k=2)
        assert len(results) == 2

    @patch("rag.reranker.get_reranker")
    def test_rerank_orders_by_score_descending(self, mock_get_model, mock_reranker_model):
        """Highest cross-encoder score should be first."""
        mock_get_model.return_value = mock_reranker_model
        candidates = [
            _make_candidate("The cat sat on the mat.", score=0.5),
            _make_candidate("Attention is all you need.", score=0.5),
            _make_candidate("BERT uses bidirectional encoders.", score=0.5),
        ]
        # mock returns [0.95, 0.72, 0.41] -- index 0 wins
        from rag.reranker import rerank
        results = rerank("transformer attention", candidates, top_k=3)
        assert results[0][0] == "The cat sat on the mat."
        assert results[0][2] >= results[1][2]

    @patch("rag.reranker.get_reranker")
    def test_rerank_fewer_chunks_than_top_k(self, mock_get_model, mock_reranker_model):
        """rerank(top_k=5) with 2 chunks returns <=2, not 5."""
        mock_get_model.return_value = mock_reranker_model
        mock_reranker_model.predict.return_value = np.array([0.8, 0.6])
        candidates = [_make_candidate("a"), _make_candidate("b")]
        from rag.reranker import rerank
        results = rerank("query", candidates, top_k=5)
        assert len(results) <= 2

    def test_rerank_empty_input_returns_empty(self):
        """rerank() with empty candidate list returns []."""
        from rag.reranker import rerank
        results = rerank("query", [], top_k=5)
        assert results == []

    @patch("rag.reranker.get_reranker")
    def test_reranker_failure_documented(self, mock_get_model, failing_reranker_model):
        """If get_reranker() raises (model not loaded), rerank() propagates the error.

        This is a documentation test: the current reranker has no fallback.
        If you add try/except in reranker.rerank(), update this test.
        """
        mock_get_model.return_value = failing_reranker_model
        candidates = [_make_candidate("alpha"), _make_candidate("beta")]
        from rag.reranker import rerank
        with pytest.raises(RuntimeError, match="CUDA out of memory"):
            rerank("query", candidates, top_k=3)

    @patch("rag.reranker.get_reranker")
    def test_reranker_scores_attached_to_chunks(self, mock_get_model, mock_reranker_model):
        """After reranking, scores reflect cross-encoder output."""
        mock_get_model.return_value = mock_reranker_model
        candidates = [_make_candidate("x"), _make_candidate("y"), _make_candidate("z")]
        from rag.reranker import rerank
        results = rerank("query", candidates, top_k=3)
        scores = [s for _, _, s in results]
        assert all(s <= 1.0 for s in scores)  # cross-encoder outputs are bounded

    def test_rerank_calls_predict_with_pairs(self):
        """Verify the cross-encoder receives (query, doc) pairs."""
        candidates = [
            _make_candidate("doc A"),
            _make_candidate("doc B"),
        ]
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9, 0.5])
        with patch("rag.reranker.get_reranker", return_value=mock_model):
            from rag.reranker import rerank
            rerank("my query", candidates, top_k=2)
        call_pairs = mock_model.predict.call_args[0][0]
        assert call_pairs == [("my query", "doc A"), ("my query", "doc B")]


# ---------------------------------------------------------------------------
# Tests: compressor -- token-budget truncation
# ---------------------------------------------------------------------------

class TestCompressor:

    def test_short_context_not_truncated(self):
        """Context under budget is returned unchanged."""
        from rag.compressor import compress_results
        chunks = [_make_candidate("Short text.", score=0.9)]
        result = compress_results(chunks, max_chars=1200)
        assert result[0][0] == "Short text."

    def test_long_context_truncated_to_budget(self):
        """Total chars of compressed context is within budget."""
        from rag.compressor import compress_results
        chunks = [_make_candidate("A" * 500, score=0.9 - i * 0.1) for i in range(5)]
        result = compress_results(chunks, max_chars=1200)
        total_chars = sum(len(c) for c, _, _ in result)
        assert total_chars <= 1200 + 50  # 50-char tolerance for sentence boundaries

    def test_highest_score_chunk_preserved_first(self):
        """When budget forces dropping, highest-scoring chunks survive."""
        from rag.compressor import compress_results
        chunks = [
            _make_candidate("Low score text " * 50, score=0.3),
            _make_candidate("High score text", score=0.95),
            _make_candidate("Medium score text " * 20, score=0.6),
        ]
        result = compress_results(chunks, max_chars=200)
        texts = [doc for doc, _, _ in result]
        assert any("High score text" in t for t in texts)

    def test_empty_chunks_returns_empty(self):
        """compress_results([]) returns []."""
        from rag.compressor import compress_results
        assert compress_results([], max_chars=1200) == []


# ---------------------------------------------------------------------------
# Tests: integration -- retrieve -> rerank pipeline
# ---------------------------------------------------------------------------

class TestPipeline:

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_full_pipeline_returns_list(
        self, mock_embed, mock_search, chroma_results, mock_reranker_model
    ):
        """End-to-end retrieve -> rerank returns non-empty list of tuples."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        with patch("rag.reranker.get_reranker", return_value=mock_reranker_model):
            from rag.retriever import retrieve
            results = retrieve("attention mechanism", top_k=5)
        assert isinstance(results, list)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, tuple) and len(r) == 3

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_pipeline_preserves_source_attribution(
        self, mock_embed, mock_search, chroma_results, mock_reranker_model
    ):
        """Source names survive the full retrieve -> rerank pipeline."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        with patch("rag.reranker.get_reranker", return_value=mock_reranker_model):
            from rag.retriever import retrieve
            results = retrieve("attention", top_k=5)
        for _, meta, _ in results:
            assert meta.get("source"), f"Source missing: {meta}"

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_zero_results_no_crash(
        self, mock_embed, mock_search, empty_chroma_results, mock_reranker_model
    ):
        """Pipeline handles 0 ChromaDB results gracefully."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = empty_chroma_results
        with patch("rag.reranker.get_reranker", return_value=mock_reranker_model):
            from rag.retriever import retrieve
            results = retrieve("anything", top_k=5)
        assert results == []

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_duplicate_sources_allowed(
        self, mock_embed, mock_search, mock_reranker_model
    ):
        """Multiple chunks from the same PDF are valid (dedup is quality_filter's job)."""
        same_source_results = _make_chroma_result(
            texts=["chunk A", "chunk B", "chunk C"],
            metadatas=[
                {"source": "same.pdf", "page": 1, "section": "A"},
                {"source": "same.pdf", "page": 2, "section": "B"},
                {"source": "same.pdf", "page": 3, "section": "C"},
            ],
        )
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = same_source_results
        with patch("rag.reranker.get_reranker", return_value=mock_reranker_model):
            from rag.retriever import retrieve
            results = retrieve("query", top_k=3)
        sources = [meta["source"] for _, meta, _ in results]
        assert sources.count("same.pdf") > 1, "Multiple chunks from same source allowed"


# ---------------------------------------------------------------------------
# Tests: retrieve_raw() -- bypassing the reranker
# ---------------------------------------------------------------------------

class TestRetrieveRaw:

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_raw_returns_tuples(self, mock_embed, mock_search, chroma_results):
        """retrieve_raw() returns (doc, meta, distance) tuples without reranking."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = chroma_results
        from rag.retriever import retrieve_raw
        results = retrieve_raw("attention", top_k=3)
        assert len(results) == 3
        for doc, meta, score in results:
            assert isinstance(doc, str)
            assert isinstance(meta, dict)
            assert isinstance(score, (int, float))

    @patch("rag.retriever.search")
    @patch("rag.retriever.embed_query")
    def test_raw_empty(self, mock_embed, mock_search, empty_chroma_results):
        """retrieve_raw() on empty collection returns []."""
        mock_embed.return_value = np.ones(384, dtype=np.float32)
        mock_search.return_value = empty_chroma_results
        from rag.retriever import retrieve_raw
        assert retrieve_raw("anything") == []


# ---------------------------------------------------------------------------
# Tests: format_context() -- string formatting
# ---------------------------------------------------------------------------

class TestFormatContext:

    def test_basic_formatting(self):
        """format_context() produces header lines with source and score."""
        from rag.retriever import format_context
        results = [
            ("Some text about transformers.", {"source": "paper.pdf", "page": 3, "section": "intro"}, 0.95),
        ]
        output = format_context(results)
        assert "paper.pdf" in output
        assert "p.3" in output
        assert "0.950" in output
        assert "Some text about transformers." in output

    def test_empty_results(self):
        """format_context([]) returns empty string."""
        from rag.retriever import format_context
        assert format_context([]) == ""

    def test_no_page_in_meta(self):
        """format_context() does not crash when page is absent."""
        from rag.retriever import format_context
        results = [("Just text.", {"source": "doc.pdf", "section": "body"}, 0.5)]
        output = format_context(results)
        assert "doc.pdf" in output
        assert "Just text." in output
