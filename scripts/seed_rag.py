from eval.data_loader import load_news
from src.rag.store import RAGStore

store = RAGStore()
count = store.ingest(load_news())
print(f"RAG seeded with {count} articles")
