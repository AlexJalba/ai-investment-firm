"""ChromaDB vector store — ingest, retrieve, cite."""
from __future__ import annotations

import hashlib

import chromadb
from chromadb.utils import embedding_functions

from src.config import get_settings
from src.observability.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "market_research"


class RAGStore:
    """Thin wrapper around ChromaDB for market research ingestion and retrieval."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._client = chromadb.PersistentClient(path=cfg.chroma_persist_dir)
        # Use OpenAI embeddings via Anthropic-compatible endpoint if available,
        # otherwise fall back to the built-in sentence-transformer model.
        try:
            ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=cfg.anthropic_api_key,
                model_name="text-embedding-3-small",
            )
        except Exception:
            ef = embedding_functions.DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest(self, articles: list[dict]) -> int:
        """Add news articles to the vector store. Returns the count added."""
        docs, ids, metas = [], [], []
        for art in articles:
            text = f"{art.get('title', '')}. {art.get('summary', '')}".strip()
            if not text or text == ".":
                continue
            doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]
            if doc_id in ids:
                continue
            docs.append(text)
            ids.append(doc_id)
            metas.append(
                {
                    "ticker": art.get("ticker") or "",
                    "url": art.get("url", ""),
                    "source": art.get("source", ""),
                    "published": art.get("published", ""),
                }
            )

        if docs:
            self._collection.upsert(documents=docs, ids=ids, metadatas=metas)
            logger.info("rag.ingested", count=len(docs))
        return len(docs)

    def retrieve(
        self,
        query: str,
        ticker: str | None = None,
        n_results: int = 5,
    ) -> list[dict]:
        """Retrieve relevant chunks. Returns list of {text, source, url, score}."""
        where = {"ticker": ticker} if ticker else None
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, self._collection.count() or 1),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("rag.retrieve_failed", error=str(e))
            return []

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append(
                {
                    "text": doc,
                    "source": meta.get("source", ""),
                    "url": meta.get("url", ""),
                    "ticker": meta.get("ticker", ""),
                    "published": meta.get("published", ""),
                    "relevance_score": round(1 - dist, 4),
                }
            )
        return chunks

    def format_citations(self, chunks: list[dict]) -> str:
        """Format retrieved chunks as a numbered citation block for agent prompts."""
        if not chunks:
            return "No relevant evidence found in the research database."
        lines = []
        for i, c in enumerate(chunks, 1):
            pub = c.get("published", "")[:10]
            source = c.get("source") or c.get("url") or "unknown"
            lines.append(f"[{i}] ({pub} via {source}): {c['text']}")
        return "\n".join(lines)
