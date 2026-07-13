"""Retrieves relevant scheme-document chunks from ChromaDB for RAG."""

import chromadb
from sentence_transformers import SentenceTransformer

try:
    from backend.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR, EMBEDDING_MODEL_NAME
except ImportError:  # allows running as `python retriever.py` from within backend/rag/
    from config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR, EMBEDDING_MODEL_NAME

_client = None
_collection = None
_model = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = _client.get_collection(CHROMA_COLLECTION_NAME)
    return _collection


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Return the top-k chunks most relevant to `query`.

    Each result dict has: text, source (filename), section (title), distance.
    """
    collection = _get_collection()
    model = _get_model()

    query_embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=k)

    hits = []
    for text, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "source": metadata["source"],
                "section": metadata["section"],
                "distance": distance,
            }
        )
    return hits


if __name__ == "__main__":
    test_queries = [
        "tax saving investment with shortest lock-in period",
        "safe options for someone close to retirement",
        "additional tax deduction beyond 80C limit",
    ]
    for q in test_queries:
        print(f"\n=== Query: {q} ===")
        for rank, hit in enumerate(retrieve(q, k=3), start=1):
            print(f"{rank}. [{hit['source']} / {hit['section']}]  (distance={hit['distance']:.4f})")
            print(f"   {hit['text'][:220].replace(chr(10), ' ')}...")
