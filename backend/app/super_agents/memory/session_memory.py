"""
Session Memory - Session-based memory management for the Super Agent.
Handles message history, context loading, and checkpoint creation.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import structlog

from app.models.models import (
    SuperAgentSession,
    SuperAgentMessage,
    SuperAgentCheckpoint,
)

logger = structlog.get_logger()

# Create a checkpoint every N interactions
CHECKPOINT_INTERVAL = 5


def _build_session_title_from_content(content: Optional[str]) -> Optional[str]:
    if not content:
        return None

    normalized = " ".join(content.strip().split())
    if not normalized:
        return None

    return normalized[:60].rstrip()


def _build_message_preview(content: Optional[str], thinking_content: Optional[str]) -> Optional[str]:
    source = content or thinking_content or ""
    normalized = " ".join(source.strip().split())
    if not normalized:
        return None

    return normalized[:120].rstrip()


class SessionMemory:
    """
    Manages session-specific memory for the Super Agent.
    Handles message history, context loading, and checkpoint creation.
    """

    @staticmethod
    async def create_session(
        db: Session,
        company_id: str,
        user_id: str,
        title: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a new Super Agent session.

        Args:
            db: Database session
            company_id: Company ID
            user_id: User ID
            title: Optional session title

        Returns:
            Session ID or None on failure
        """
        try:
            session = SuperAgentSession(
                company_id=company_id,
                user_id=user_id,
                title=title or "Nova conversa",
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            logger.info(
                "Super Agent session created",
                session_id=session.id,
                company_id=company_id,
                user_id=user_id,
            )
            return session.id

        except Exception as e:
            logger.error("Failed to create session", error=str(e))
            db.rollback()
            return None

    @staticmethod
    async def get_session(
        db: Session,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get session details.

        Args:
            db: Database session
            session_id: Session ID

        Returns:
            Session dict or None
        """
        session = db.query(SuperAgentSession).filter(
            SuperAgentSession.id == session_id
        ).first()

        if not session:
            return None

        return {
            "id": session.id,
            "company_id": session.company_id,
            "user_id": session.user_id,
            "title": session.title,
            "is_active": session.is_active,
            "interaction_count": session.interaction_count,
            "last_checkpoint_at": session.last_checkpoint_at,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    @staticmethod
    async def get_recent_messages(
        db: Session,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from a session.

        Args:
            db: Database session
            session_id: Session ID
            limit: Maximum number of messages

        Returns:
            List of message dicts
        """
        messages = db.query(SuperAgentMessage).filter(
            SuperAgentMessage.session_id == session_id
        ).order_by(
            desc(SuperAgentMessage.created_at)
        ).limit(limit).all()

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_name": msg.tool_name,
                "tool_input": msg.tool_input,
                "tool_output": msg.tool_output,
                "thinking_content": msg.thinking_content,
                "extra_data": msg.extra_data,
                "created_at": msg.created_at,
            }
            for msg in reversed(messages)
        ]

    @staticmethod
    async def load_session_context(
        db: Session,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Load full session context including recent messages and latest checkpoint.

        Args:
            db: Database session
            session_id: Session ID

        Returns:
            Session context dict
        """
        session = await SessionMemory.get_session(db, session_id)
        if not session:
            return {"error": "Session not found"}

        recent_messages = await SessionMemory.get_recent_messages(db, session_id)
        latest_checkpoint = await SessionMemory.get_latest_checkpoint(db, session_id)

        return {
            "session": session,
            "recent_messages": recent_messages,
            "latest_checkpoint": latest_checkpoint,
        }

    @staticmethod
    async def add_message(
        db: Session,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[str] = None,
        thinking_content: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Add a message to the session.

        Args:
            db: Database session
            session_id: Session ID
            role: Message role (user, assistant, system, tool)
            content: Message content
            tool_name: Tool name if role=tool
            tool_input: Tool input
            tool_output: Tool output
            thinking_content: Agent thinking content
            metadata: Additional metadata

        Returns:
            Message ID or None on failure
        """
        try:
            session = db.query(SuperAgentSession).filter(
                SuperAgentSession.id == session_id
            ).first()

            if not session:
                logger.error("Failed to add message: session not found", session_id=session_id)
                return None

            message = SuperAgentMessage(
                session_id=session_id,
                role=role,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                thinking_content=thinking_content,
                extra_data=extra_data,
                created_at=datetime.now(timezone.utc),
            )
            db.add(message)
            session.updated_at = datetime.now(timezone.utc)

            # Increment interaction count for user messages
            if role == "user":
                session.interaction_count += 1

                if session.title in (None, "", "Nova conversa"):
                    generated_title = _build_session_title_from_content(content)
                    if generated_title:
                        session.title = generated_title

            db.commit()
            db.refresh(message)

            return message.id

        except Exception as e:
            logger.error("Failed to add message", error=str(e))
            db.rollback()
            return None

    @staticmethod
    async def should_create_checkpoint(
        db: Session,
        session_id: str,
    ) -> bool:
        """
        Check if a checkpoint should be created (every N interactions).

        Args:
            db: Database session
            session_id: Session ID

        Returns:
            True if checkpoint should be created
        """
        session = db.query(SuperAgentSession).filter(
            SuperAgentSession.id == session_id
        ).first()

        if not session:
            return False

        current_count = session.interaction_count
        last_checkpoint = session.last_checkpoint_at

        return (current_count - last_checkpoint) >= CHECKPOINT_INTERVAL

    @staticmethod
    async def create_checkpoint(
        db: Session,
        session_id: str,
        summary: str,
        context_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create a checkpoint for the session.

        Args:
            db: Database session
            session_id: Session ID
            summary: AI-generated summary
            context_snapshot: Optional context snapshot

        Returns:
            Checkpoint ID or None on failure
        """
        try:
            session = db.query(SuperAgentSession).filter(
                SuperAgentSession.id == session_id
            ).first()

            if not session:
                return None

            checkpoint = SuperAgentCheckpoint(
                session_id=session_id,
                interaction_number=session.interaction_count,
                summary=summary,
                context_snapshot=context_snapshot,
            )
            db.add(checkpoint)

            # Update last checkpoint
            session.last_checkpoint_at = session.interaction_count

            db.commit()
            db.refresh(checkpoint)

            logger.info(
                "Checkpoint created",
                session_id=session_id,
                interaction_number=session.interaction_count,
            )
            return checkpoint.id

        except Exception as e:
            logger.error("Failed to create checkpoint", error=str(e))
            db.rollback()
            return None

    @staticmethod
    async def get_latest_checkpoint(
        db: Session,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint for a session.

        Args:
            db: Database session
            session_id: Session ID

        Returns:
            Checkpoint dict or None
        """
        checkpoint = db.query(SuperAgentCheckpoint).filter(
            SuperAgentCheckpoint.session_id == session_id
        ).order_by(
            desc(SuperAgentCheckpoint.interaction_number)
        ).first()

        if not checkpoint:
            return None

        return {
            "id": checkpoint.id,
            "session_id": checkpoint.session_id,
            "interaction_number": checkpoint.interaction_number,
            "summary": checkpoint.summary,
            "context_snapshot": checkpoint.context_snapshot,
            "created_at": checkpoint.created_at,
        }

    @staticmethod
    async def list_sessions(
        db: Session,
        company_id: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a company.

        Args:
            db: Database session
            company_id: Company ID
            user_id: Optional user ID filter
            limit: Maximum sessions

        Returns:
            List of session dicts
        """
        stmt = db.query(SuperAgentSession).filter(
            SuperAgentSession.company_id == company_id,
            SuperAgentSession.is_active == True,
        )

        if user_id:
            stmt = stmt.filter(SuperAgentSession.user_id == user_id)

        sessions = stmt.order_by(
            desc(func.coalesce(SuperAgentSession.updated_at, SuperAgentSession.created_at))
        ).limit(limit).all()

        serialized_sessions = []

        for session in sessions:
            latest_message = db.query(SuperAgentMessage).filter(
                SuperAgentMessage.session_id == session.id
            ).order_by(desc(SuperAgentMessage.created_at)).first()

            serialized_sessions.append(
                {
                    "id": session.id,
                    "company_id": session.company_id,
                    "user_id": session.user_id,
                    "title": session.title,
                    "is_active": session.is_active,
                    "interaction_count": session.interaction_count,
                    "last_checkpoint_at": session.last_checkpoint_at,
                    "last_message_preview": _build_message_preview(
                        latest_message.content if latest_message else None,
                        latest_message.thinking_content if latest_message else None,
                    ),
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                }
            )

        return serialized_sessions
