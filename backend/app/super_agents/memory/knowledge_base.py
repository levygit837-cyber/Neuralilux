"""
Knowledge Base - Cross-session knowledge storage and retrieval.
Uses simple text matching (LIKE/ILIKE) instead of embeddings.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
import structlog

from app.models.models import SuperAgentKnowledge

logger = structlog.get_logger()


class KnowledgeBase:
    """
    Manages cross-session knowledge storage and retrieval for the Super Agent.
    Uses PostgreSQL LIKE/ILIKE for text matching (no embeddings required).
    """

    @staticmethod
    async def search(
        db: Session,
        company_id: str,
        query: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using text matching.

        Args:
            db: Database session
            company_id: Company ID to scope search
            query: Search query text
            category: Optional category filter

        Returns:
            List of matching knowledge items
        """
        try:
            stmt = db.query(SuperAgentKnowledge).filter(
                SuperAgentKnowledge.company_id == company_id
            )

            if category:
                stmt = stmt.filter(SuperAgentKnowledge.category == category)

            # Text matching on key and value
            search_pattern = f"%{query}%"
            stmt = stmt.filter(
                or_(
                    SuperAgentKnowledge.key.ilike(search_pattern),
                    SuperAgentKnowledge.value.ilike(search_pattern),
                )
            )

            # Order by relevance (access count) and recency
            stmt = stmt.order_by(
                SuperAgentKnowledge.access_count.desc(),
                SuperAgentKnowledge.updated_at.desc(),
            ).limit(10)

            results = stmt.all()

            # Update access counts
            for item in results:
                item.access_count += 1
            db.commit()

            logger.info(
                "Knowledge search completed",
                company_id=company_id,
                query=query[:50],
                results_count=len(results),
            )

            return [
                {
                    "id": item.id,
                    "category": item.category,
                    "key": item.key,
                    "value": item.value,
                    "confidence": item.confidence,
                    "access_count": item.access_count,
                }
                for item in results
            ]

        except Exception as e:
            logger.error("Knowledge search failed", error=str(e))
            return []

    @staticmethod
    async def store(
        db: Session,
        company_id: str,
        category: str,
        key: str,
        value: str,
        source_session_id: Optional[str] = None,
        confidence: int = 100,
    ) -> Optional[str]:
        """
        Store or update knowledge in the knowledge base.

        Args:
            db: Database session
            company_id: Company ID
            category: Knowledge category
            key: Knowledge key
            value: Knowledge content
            source_session_id: Optional source session ID
            confidence: Confidence score (0-100)

        Returns:
            Knowledge item ID or None on failure
        """
        try:
            # Check if knowledge already exists
            existing = db.query(SuperAgentKnowledge).filter(
                SuperAgentKnowledge.company_id == company_id,
                SuperAgentKnowledge.category == category,
                SuperAgentKnowledge.key == key,
            ).first()

            if existing:
                existing.value = value
                existing.confidence = confidence
                existing.source_session_id = source_session_id
                db.commit()
                db.refresh(existing)
                logger.info(
                    "Knowledge updated",
                    knowledge_id=existing.id,
                    category=category,
                    key=key,
                )
                return existing.id

            # Create new knowledge item
            knowledge = SuperAgentKnowledge(
                company_id=company_id,
                category=category,
                key=key,
                value=value,
                source_session_id=source_session_id,
                confidence=confidence,
            )
            db.add(knowledge)
            db.commit()
            db.refresh(knowledge)

            logger.info(
                "Knowledge stored",
                knowledge_id=knowledge.id,
                category=category,
                key=key,
            )
            return knowledge.id

        except Exception as e:
            logger.error("Knowledge store failed", error=str(e))
            db.rollback()
            return None

    @staticmethod
    async def get(
        db: Session,
        company_id: str,
        category: str,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific knowledge item by category and key.

        Args:
            db: Database session
            company_id: Company ID
            category: Knowledge category
            key: Knowledge key

        Returns:
            Knowledge item dict or None
        """
        try:
            item = db.query(SuperAgentKnowledge).filter(
                SuperAgentKnowledge.company_id == company_id,
                SuperAgentKnowledge.category == category,
                SuperAgentKnowledge.key == key,
            ).first()

            if not item:
                return None

            # Update access count
            item.access_count += 1
            db.commit()

            return {
                "id": item.id,
                "category": item.category,
                "key": item.key,
                "value": item.value,
                "confidence": item.confidence,
                "access_count": item.access_count,
            }

        except Exception as e:
            logger.error("Knowledge get failed", error=str(e))
            return None