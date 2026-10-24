"""
Gravação compartilhada entre o webhook ao vivo e a importação de histórico: Contact, Conversation e Message.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.models.base import generate_uuid
from app.whatsapp.webhook_parser import ParsedContent, is_group_chat

_INSERT_BY_DIALECT = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}


def _insert_if_absent(db: Session, model: type, values: dict[str, Any], unique_columns: list[str]) -> bool:
    """`INSERT ... ON CONFLICT DO NOTHING` na unicidade `unique_columns`; True se a linha entrou.

    O webhook e a importação de histórico criam o mesmo Contact/Conversation em processos diferentes: um
    SELECT-then-INSERT deixaria os dois inserirem. Aqui o perdedor da corrida não recebe erro nem desfaz a
    transação de quem chamou (um `IntegrityError` forçaria `rollback`): o banco ignora o insert e quem chama
    relê a linha do vencedor. No Postgres, se o vencedor ainda não confirmou, o insert espera por ele.
    """
    insert = _INSERT_BY_DIALECT[db.get_bind().dialect.name]
    statement = (
        insert(model).values(**values).on_conflict_do_nothing(index_elements=unique_columns).returning(model.id)
    )
    return db.execute(statement).first() is not None


def phone_number_of(remote_jid: str) -> str:
    """Parte numérica do JID. Num grupo (`123-456@g.us`) é o número de quem o criou."""
    local_part = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
    return local_part.split("-")[0][:20]


def get_or_create_contact(
    db: Session,
    instance: Instance,
    remote_jid: str,
    *,
    push_name: Optional[str] = None,
    name: Optional[str] = None,
) -> Contact:
    """Contact do JID. `push_name` é o nome que a pessoa se deu; `name` (ex.: assunto do grupo) tem precedência.

    Quem chama passa `None` quando o pushName não é do Contact: mensagem `fromMe` (é o nosso número) ou
    mensagem de grupo (é o participante, não o grupo). O nome só é preenchido se ainda não houver um de verdade.
    """
    phone_number = phone_number_of(remote_jid)
    best_name = name or push_name

    def find() -> Optional[Contact]:
        return db.query(Contact).filter(
            Contact.instance_id == instance.id,
            Contact.remote_jid == remote_jid,
        ).first()

    contact = find()
    if contact is None:
        now = datetime.now(timezone.utc)
        inserted = _insert_if_absent(
            db,
            Contact,
            {
                "id": generate_uuid(),
                "instance_id": instance.id,
                "phone_number": phone_number,
                "remote_jid": remote_jid,
                "name": best_name or phone_number,
                "push_name": push_name,
                "created_at": now,
                "updated_at": now,
            },
            ["instance_id", "remote_jid"],
        )
        contact = find()  # quem perdeu a corrida lê a linha do vencedor e segue como Contact existente
        if inserted:
            return contact
    if push_name:
        contact.push_name = push_name
    if best_name and (not contact.name or contact.name == contact.phone_number):
        contact.name = best_name
    return contact


def get_or_create_conversation(
    db: Session, instance: Instance, contact: Contact, remote_jid: str
) -> tuple[Conversation, bool]:
    """Conversation do Contact na Instance e se ela acabou de ser criada (à prova de corrida, como o Contact)."""

    def find() -> Optional[Conversation]:
        return db.query(Conversation).filter(
            Conversation.instance_id == instance.id,
            Conversation.contact_id == contact.id,
        ).first()

    is_group = is_group_chat(remote_jid)
    conversation = find()
    created = False
    if conversation is None:
        now = datetime.now(timezone.utc)
        created = _insert_if_absent(
            db,
            Conversation,
            {
                "id": generate_uuid(),
                "instance_id": instance.id,
                "contact_id": contact.id,
                "remote_jid": remote_jid,
                "is_active": True,
                "is_group": is_group,
                "created_at": now,
                "updated_at": now,
            },
            ["instance_id", "contact_id"],
        )
        conversation = find()
    if not created and is_group and not conversation.is_group:
        conversation.is_group = True
    return conversation, created


def new_message(
    instance: Instance,
    conversation: Conversation,
    remote_jid: str,
    message_id: Optional[str],
    parsed: ParsedContent,
    from_me: bool,
    timestamp: datetime,
    *,
    sender_name: Optional[str] = None,
) -> Message:
    return Message(
        id=generate_uuid(),
        instance_id=instance.id,
        conversation_id=conversation.id,
        remote_jid=remote_jid,
        message_id=message_id,
        message_type=parsed.message_type,
        content=parsed.content,
        direction="outgoing" if from_me else "incoming",
        status="sent",
        is_from_me=from_me,
        sender_name=sender_name,
        timestamp=timestamp,
    )
