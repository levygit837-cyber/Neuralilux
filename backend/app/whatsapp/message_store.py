"""
Gravação compartilhada entre o webhook ao vivo e a importação de histórico: Contact, Conversation e Message.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.models.base import generate_uuid
from app.whatsapp.webhook_parser import ParsedContent, is_group_chat


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
    contact = db.query(Contact).filter(
        Contact.instance_id == instance.id,
        Contact.remote_jid == remote_jid,
    ).first()
    best_name = name or push_name
    if contact is None:
        now = datetime.now(timezone.utc)
        contact = Contact(
            instance_id=instance.id,
            phone_number=phone_number,
            remote_jid=remote_jid,
            name=best_name or phone_number,
            push_name=push_name,
            created_at=now,
            updated_at=now,
        )
        db.add(contact)
        db.flush()
        return contact
    if push_name:
        contact.push_name = push_name
    if best_name and (not contact.name or contact.name == contact.phone_number):
        contact.name = best_name
    return contact


def get_or_create_conversation(
    db: Session, instance: Instance, contact: Contact, remote_jid: str
) -> tuple[Conversation, bool]:
    """Conversation do Contact na Instance e se ela acabou de ser criada."""
    conversation = db.query(Conversation).filter(
        Conversation.instance_id == instance.id,
        Conversation.contact_id == contact.id,
    ).first()
    is_group = is_group_chat(remote_jid)
    if conversation is not None:
        if is_group and not conversation.is_group:
            conversation.is_group = True
        return conversation, False
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        instance_id=instance.id,
        contact_id=contact.id,
        remote_jid=remote_jid,
        is_active=True,
        is_group=is_group,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    return conversation, True


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
