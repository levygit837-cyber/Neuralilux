"""Qdrant vector store wrapper for RAG."""
import os
from typing import List, Dict, Any, Optional
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue

logger = structlog.get_logger()

COLLECTION_NAME = "company_rules"


class RAGVectorStore:
    """Wrapper for Qdrant vector store."""

    def __init__(self, qdrant_url: str = None, qdrant_api_key: str = None):
        qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY")

        try:
            if qdrant_api_key:
                self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            else:
                self.client = QdrantClient(host=qdrant_url.replace("http://", "").replace("https://", "").split(":")[0],
                                           port=int(qdrant_url.split(":")[-1]) if ":" in qdrant_url else 6333)
        except Exception:
            self.client = QdrantClient()
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection", collection=COLLECTION_NAME)

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        company_id: str,
    ) -> List[str]:
        """Add documents to the vector store."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")

        points = []
        for idx, doc in enumerate(documents):
            text = doc.get("content", "")
            if not text:
                continue

            vector = model.encode(text).tolist()
            point_id = f"{company_id}_{doc.get('id', idx)}"

            points.append({
                "id": point_id,
                "vector": vector,
                "payload": {
                    "company_id": company_id,
                    "title": doc.get("title", ""),
                    "content": text,
                    "category": doc.get("category", "general"),
                },
            })

        if points:
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
            )
            logger.info("Added documents to vector store", count=len(points), company_id=company_id)

        return [p["id"] for p in points]

    def search(
        self,
        query: str,
        company_id: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_vector = model.encode(query).tolist()

        filter_conditions = [FieldCondition(key="company_id", match=MatchValue(value=company_id))]
        if category:
            filter_conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=Filter(must=filter_conditions),
            limit=limit,
        )

        return [
            {
                "id": r.id,
                "title": r.payload.get("title"),
                "content": r.payload.get("content"),
                "category": r.payload.get("category"),
                "score": r.score,
            }
            for r in results
        ]

    def delete_by_company(self, company_id: str):
        """Delete all documents for a company."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="company_id", match=MatchValue(value=company_id))]
            ),
        )
        logger.info("Deleted company documents", company_id=company_id)

    def delete_by_id(self, point_id: str):
        """Delete a specific document."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[point_id],
        )


_rag_store: Optional[RAGVectorStore] = None


def get_rag_store() -> RAGVectorStore:
    """Get singleton RAG vector store instance."""
    global _rag_store
    if _rag_store is None:
        _rag_store = RAGVectorStore()
    return _rag_store
