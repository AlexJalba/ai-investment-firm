"""Tests for the RAG store."""
import os


def test_ingest_and_retrieve(tmp_path):
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")

    import src.config as cfg_module
    cfg_module._settings = None

    from src.rag.store import RAGStore

    store = RAGStore()
    articles = [
        {
            "ticker": "AAPL",
            "title": "Apple beats Q4 earnings estimates",
            "summary": "Apple Inc reported revenue of $90 billion, beating consensus by 5%.",
            "url": "https://example.com/aapl",
            "source": "TestSource",
            "published": "2024-01-15",
        }
    ]
    count = store.ingest(articles)
    assert count == 1

    results = store.retrieve("Apple earnings revenue", ticker="AAPL", n_results=1)
    assert len(results) == 1
    assert "Apple" in results[0]["text"]
    assert results[0]["relevance_score"] > 0


def test_format_citations():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

    from src.rag.store import RAGStore

    store = RAGStore.__new__(RAGStore)
    chunks = [
        {"text": "Revenue up 12%", "source": "Bloomberg", "url": "", "published": "2024-01-10", "relevance_score": 0.9},
    ]
    output = store.format_citations(chunks)
    assert "[1]" in output
    assert "Bloomberg" in output


def test_empty_citations():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

    from src.rag.store import RAGStore

    store = RAGStore.__new__(RAGStore)
    output = store.format_citations([])
    assert "No relevant evidence" in output
