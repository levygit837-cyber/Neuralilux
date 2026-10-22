"""Handoff: abrir, assumir, devolver ao Agent e expirar por falta de Attendant.

O estado mora na Conversation (`human_in_loop`, `human_handoff_reason`, `ticket_id`) e o Ticket guarda quem
atende (`assigned_to`), quando o Attendant agiu por último (`attendant_activity_at`) e como terminou
(`closed` = devolvido por um Attendant, `expired` = timeout da Company).

As funções de banco são síncronas e fazem commit; `announce` publica `handoff_updated` para a UI em tempo real.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.agent.clock import utc_now
from app.core import database
from app.models import Company, Conversation, Instance, Message, Ticket, User

logger = structlog.get_logger()

# Ticket.agent_type é obrigatório; o Agent é um só por Company, então o valor é neutro.
HANDOFF_AGENT_TYPE = "whatsapp_agent"
OPEN_STATUSES = ("open", "in_progress")
DEFAULT_TIMEOUT_HOURS = 4


def _aware(value: datetime) -> datetime:
    """SQLite devolve datetimes sem fuso; tudo é gravado em UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def publish_event(event: dict[str, Any]) -> None:
    from app.realtime.event_bus import realtime_event_bus

    await realtime_event_bus.publish(event)


# ---------- transições ----------


def last_incoming_content(db: Session, conversation: Conversation) -> str | None:
    message = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.direction == "incoming", Message.content.isnot(None))
        .order_by(Message.timestamp.desc())
        .first()
    )
    return message.content if message else None


def open_handoff(db: Session, conversation: Conversation, reason: str, *, attendant: User | None = None) -> Ticket:
    """Liga o Handoff e abre o Ticket. Com `attendant`, o Ticket já nasce atribuído a ele (`in_progress`)."""
    now = utc_now()
    ticket = Ticket(
        conversation_id=conversation.id,
        instance_id=conversation.instance_id,
        contact_id=conversation.contact_id,  # FK de contacts.id, nunca o remote_jid
        agent_type=HANDOFF_AGENT_TYPE,
        reason=reason,
        content=last_incoming_content(db, conversation) or reason,
        status="in_progress" if attendant else "open",
        assigned_to=attendant.id if attendant else None,
        attendant_activity_at=now if attendant else None,
    )
    db.add(ticket)
    db.flush()
    conversation.human_in_loop = True
    conversation.human_handoff_reason = reason
    conversation.ticket_id = ticket.id
    db.commit()
    return ticket


def assume(db: Session, conversation: Conversation, attendant: User, reason: str | None = None) -> Ticket:
    """O Attendant assume a Conversation. Sem Ticket aberto (assumir direto do Agent), abre um."""
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.human_in_loop and conversation.ticket_id else None
    if ticket is None or ticket.status not in OPEN_STATUSES:
        return open_handoff(
            db, conversation, reason or f"Atendimento assumido por {attendant.full_name or attendant.email}", attendant=attendant
        )
    now = utc_now()
    ticket.assigned_to = attendant.id
    ticket.status = "in_progress"
    ticket.attendant_activity_at = now
    ticket.updated_at = now
    db.commit()
    return ticket


def release(db: Session, conversation: Conversation, *, status: str = "closed") -> Ticket | None:
    """Devolve a Conversation ao Agent e fecha o Ticket aberto (`closed`, ou `expired` no timeout)."""
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.ticket_id else None
    now = utc_now()
    if ticket is not None and ticket.status in OPEN_STATUSES:
        ticket.status = status
        ticket.closed_at = now
        ticket.updated_at = now
    conversation.human_in_loop = False
    conversation.human_handoff_reason = None
    conversation.ticket_id = None
    db.commit()
    return ticket


def record_attendant_activity(db: Session, conversation: Conversation) -> None:
    """Um Attendant escreveu na Conversation em Handoff: reinicia a contagem do timeout."""
    if not conversation.human_in_loop or not conversation.ticket_id:
        return
    ticket = db.get(Ticket, conversation.ticket_id)
    if ticket is None:
        return
    ticket.attendant_activity_at = utc_now()
    db.commit()


# ---------- timeout ----------


def _last_touch(db: Session, conversation: Conversation) -> datetime | None:
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.ticket_id else None
    if ticket is not None:
        return _aware(max(t for t in (ticket.created_at, ticket.attendant_activity_at) if t is not None))
    stamp = conversation.updated_at or conversation.created_at  # Handoff antigo, sem Ticket
    return _aware(stamp) if stamp else None


def is_overdue(db: Session, conversation: Conversation, company: Company | None, now: datetime | None = None) -> bool:
    """True se a Conversation está em Handoff e nenhum Attendant agiu dentro do timeout da Company."""
    if not conversation.human_in_loop or company is None:
        return False
    touched = _last_touch(db, conversation)
    if touched is None:
        return False
    timeout = timedelta(hours=company.handoff_timeout_hours or DEFAULT_TIMEOUT_HOURS)
    return (now or utc_now()) - touched >= timeout


async def announce(instance: Instance | None, conversation: Conversation, change: str, ticket: Ticket | None) -> None:
    """Avisa a UI (`handoff_updated`). `change`: assumed | released | expired. Falha de notificação só loga."""
    if instance is None:
        return
    try:
        await publish_event(
            {
                "instance_name": instance.name,
                "type": "handoff_updated",
                "payload": {
                    "conversation_id": conversation.id,
                    "remote_jid": conversation.remote_jid,
                    "instance_id": conversation.instance_id,
                    "ticket_id": ticket.id if ticket else None,
                    "change": change,
                    "human_in_loop": bool(conversation.human_in_loop),
                    "assigned_to": ticket.assigned_to if ticket and conversation.human_in_loop else None,
                    "timestamp": utc_now().isoformat(),
                },
            }
        )
    except Exception as exc:  # o estado já está gravado
        logger.warning("Failed to publish handoff update", conversation_id=conversation.id, change=change, error=str(exc))


async def expire_if_due(db: Session, conversation: Conversation, instance: Instance, now: datetime | None = None) -> bool:
    """Devolve ao Agent uma Conversation cujo Handoff passou do timeout. True se devolveu."""
    company = db.get(Company, instance.company_id) if instance.company_id else None
    if not is_overdue(db, conversation, company, now):
        return False
    ticket = release(db, conversation, status="expired")
    logger.info("Handoff expired, Conversation back to the Agent", conversation_id=conversation.id)
    await announce(instance, conversation, "expired", ticket)
    return True


async def expire_overdue(db: Session, now: datetime | None = None) -> int:
    """Expira todos os Handoffs vencidos. Devolve quantos voltaram ao Agent."""
    rows = (
        db.query(Conversation, Instance)
        .join(Instance, Instance.id == Conversation.instance_id)
        .filter(Conversation.human_in_loop.is_(True), Instance.company_id.isnot(None))
        .all()
    )
    expired = 0
    for conversation, instance in rows:
        if await expire_if_due(db, conversation, instance, now):
            expired += 1
    return expired


async def sweep_forever(interval_seconds: int) -> None:
    """Loop do worker: expira Handoffs vencidos a cada `interval_seconds`, até ser cancelado."""
    while True:
        db = database.SessionLocal()
        try:
            await expire_overdue(db)
        except Exception:
            db.rollback()
            logger.exception("Handoff sweep failed")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)
