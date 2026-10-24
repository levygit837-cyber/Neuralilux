"""Escritas na Conversation. Cada função comita uma vez."""
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models import Conversation


def mark_read(db: Session, conversation: Conversation) -> None:
    """Zera as não lidas da Conversation."""
    conversation.unread_count = 0
    commit_or_rollback(db)
