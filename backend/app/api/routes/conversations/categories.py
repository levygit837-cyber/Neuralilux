"""Categorias da lista de Conversations (Todas, Não lidas, Grupos, IA, Humano) e seus contadores."""
from typing import Literal

from sqlalchemy import Integer, case, func, or_, select
from sqlalchemy.orm import Query, Session

from app.models import Contact, Conversation, Instance
from app.schemas.chat_state import ConversationCounts

Category = Literal["all", "unread", "groups", "ai", "human"]


def _agent_instances():
    return select(Instance.id).where(Instance.agent_enabled.is_(True))


def category_filter(category: Category):
    """Condição SQL da categoria; `None` para `all`."""
    if category == "unread":
        return Conversation.unread_count > 0
    if category == "groups":
        return Conversation.is_group.is_(True)
    if category == "human":
        return Conversation.human_in_loop.is_(True)
    if category == "ai":
        return (
            Conversation.is_group.is_(False)
            & Conversation.human_in_loop.is_(False)
            & Conversation.instance_id.in_(_agent_instances())
        )
    return None


def apply_category(query: Query, category: Category) -> Query:
    condition = category_filter(category)
    return query if condition is None else query.filter(condition)


def apply_search(query: Query, term: str) -> Query:
    """Nome, telefone, pushName ou prévia da última mensagem. Subquery em vez de join: não duplica linhas."""
    pattern = f"%{term}%"
    matching_contacts = select(Contact.id).where(
        or_(
            Contact.name.ilike(pattern),
            Contact.phone_number.ilike(pattern),
            Contact.push_name.ilike(pattern),
        )
    )
    return query.filter(
        or_(Conversation.contact_id.in_(matching_contacts), Conversation.last_message_preview.ilike(pattern))
    )


def category_counts(db: Session, instance_id: str) -> ConversationCounts:
    """Contadores da Instance, sem as arquivadas.

    `unread_messages` (o selo do menu) soma só as conversas individuais: grupos acumulam milhares de não lidas
    que não são atendimento e esconderiam as que importam.
    """

    def count_if(condition):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    unread = case((Conversation.is_group.is_(True), 0), else_=func.coalesce(Conversation.unread_count, 0))
    row = (
        db.query(
            func.count(Conversation.id),
            count_if(category_filter("unread")),
            count_if(category_filter("groups")),
            count_if(category_filter("ai")),
            count_if(category_filter("human")),
            func.coalesce(func.sum(unread), 0).cast(Integer),
        )
        .filter(
            Conversation.instance_id == instance_id,
            or_(Conversation.is_archived.is_(None), Conversation.is_archived.is_(False)),
        )
        .one()
    )
    keys = ("all", "unread", "groups", "ai", "human", "unread_messages")
    return ConversationCounts(**{key: int(value or 0) for key, value in zip(keys, row)})
