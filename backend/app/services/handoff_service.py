"""Handoff: abrir, assumir, devolver ao Agent e expirar por falta de Attendant.

O estado mora na Conversation (`human_in_loop`, `human_handoff_reason`, `ticket_id`) e o Ticket guarda quem
atende (`assigned_to`), quando o Attendant agiu por último (`attendant_activity_at`) e como terminou
(`closed` = devolvido por um Attendant, `expired` = timeout da Company).

API e sweeper do worker mexem na mesma Conversation ao mesmo tempo, então toda transição é um UPDATE
condicional no banco (`WHERE human_in_loop = ...`) e só quem muda a linha (`rowcount == 1`) age e avisa a UI.
Um Ticket já `closed` nunca vira `expired`. Os testes injetam `now=`; sem ele vale `clock.utc_now()`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agent import clock
from app.core import database
from app.models import Company, Conversation, Instance, Message, Ticket, User
from app.realtime.events import HandoffUpdated
from app.realtime.publish import publish_event

logger = structlog.get_logger()

# Ticket.agent_type é obrigatório; o Agent é um só por Company, então o valor é neutro.
HANDOFF_AGENT_TYPE = "whatsapp_agent"
OPEN_STATUSES = ("open", "in_progress")
DEFAULT_TIMEOUT_HOURS = 4


class HeldByAnotherAttendant(Exception):
    """Outro Attendant já segura a Conversation (a API responde 409)."""


@dataclass(frozen=True)
class Released:
    """Resultado de uma devolução que de fato aconteceu; `ticket` é None em Handoff antigo, sem Ticket."""

    ticket: Ticket | None


def _aware(value: datetime) -> datetime:
    """SQLite devolve datetimes sem fuso; tudo é gravado em UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def in_handoff(db: Session, conversation_id: str) -> bool:
    """A Conversation está em Handoff agora? Única regra da checagem: executor, TurnRunner e recuperação a usam.

    Lê do banco, não do objeto: um Attendant pode ter assumido depois que a Conversation foi carregada.
    """
    return bool(db.query(Conversation.human_in_loop).filter(Conversation.id == conversation_id).scalar())


# ---------- transições ----------


def last_incoming_content(db: Session, conversation: Conversation) -> str | None:
    message = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.direction == "incoming", Message.content.isnot(None))
        .order_by(Message.timestamp.desc())
        .first()
    )
    return message.content if message else None


def open_handoff(
    db: Session,
    conversation: Conversation,
    reason: str,
    *,
    attendant: User | None = None,
    now: datetime | None = None,
) -> Ticket | None:
    """Liga o Handoff e abre o Ticket. Com `attendant`, o Ticket já nasce atribuído a ele (`in_progress`).

    Devolve None, sem criar nada, se outra requisição abriu o Handoff antes. Um Handoff antigo, ligado sem Ticket,
    não conta como aberto: ele ganha o Ticket.
    """
    now = now or clock.utc_now()
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
    switched = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation.id,
            or_(Conversation.human_in_loop.is_(False), Conversation.ticket_id.is_(None)),
        )
        .update(
            {"human_in_loop": True, "human_handoff_reason": reason, "ticket_id": ticket.id},
            synchronize_session=False,
        )
    )
    if switched != 1:
        db.rollback()
        return None
    db.commit()
    return ticket


def assume(
    db: Session,
    conversation: Conversation,
    attendant: User,
    reason: str | None = None,
    *,
    now: datetime | None = None,
) -> Ticket:
    """O Attendant assume a Conversation. Sem Ticket aberto (assumir direto do Agent), abre um.

    Idempotente para o mesmo Attendant. Levanta `HeldByAnotherAttendant` se outro já assumiu.
    """
    now = now or clock.utc_now()
    fallback_reason = reason or f"Atendimento assumido por {attendant.full_name or attendant.email}"
    for _attempt in range(2):  # a 2ª volta cobre outra requisição abrindo o Handoff entre a leitura e a escrita
        ticket_id = (
            db.query(Conversation.ticket_id)
            .filter(Conversation.id == conversation.id, Conversation.human_in_loop.is_(True))
            .scalar()
        )
        ticket = db.get(Ticket, ticket_id) if ticket_id else None
        if ticket is None or ticket.status not in OPEN_STATUSES:
            opened = open_handoff(db, conversation, fallback_reason, attendant=attendant, now=now)
            if opened is not None:
                return opened
            continue
        claimed = (
            db.query(Ticket)
            .filter(
                Ticket.id == ticket.id,
                Ticket.status.in_(OPEN_STATUSES),
                or_(Ticket.assigned_to.is_(None), Ticket.assigned_to == attendant.id),
            )
            .update(
                {"assigned_to": attendant.id, "status": "in_progress", "attendant_activity_at": now, "updated_at": now},
                synchronize_session=False,
            )
        )
        db.commit()
        if claimed != 1:
            raise HeldByAnotherAttendant(ticket.id)
        db.refresh(ticket)
        return ticket
    raise HeldByAnotherAttendant(conversation.id)


def release(
    db: Session,
    conversation: Conversation,
    *,
    status: str = "closed",
    now: datetime | None = None,
    only_ticket_id: str | None = None,
) -> Released | None:
    """Devolve a Conversation ao Agent e fecha o Ticket aberto (`closed`, ou `expired` no timeout).

    Devolve None, sem mudar nada, quando outra requisição já devolveu ou quando `only_ticket_id` não é mais o
    Ticket da Conversation (o timeout julgou um Handoff que já acabou, e talvez outro tenha começado).
    """
    now = now or clock.utc_now()
    ticket_id = db.query(Conversation.ticket_id).filter(Conversation.id == conversation.id).scalar()
    if only_ticket_id is not None and ticket_id != only_ticket_id:
        db.rollback()
        return None
    same_ticket = Conversation.ticket_id == ticket_id if ticket_id else Conversation.ticket_id.is_(None)
    switched = (
        db.query(Conversation)
        .filter(Conversation.id == conversation.id, Conversation.human_in_loop.is_(True), same_ticket)
        .update(
            {"human_in_loop": False, "human_handoff_reason": None, "ticket_id": None},
            synchronize_session=False,
        )
    )
    if switched != 1:
        db.rollback()
        return None
    if ticket_id:
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.status.in_(OPEN_STATUSES)).update(
            {"status": status, "closed_at": now, "updated_at": now}, synchronize_session=False
        )
    db.commit()
    return Released(ticket=db.get(Ticket, ticket_id) if ticket_id else None)


def record_attendant_activity(db: Session, conversation: Conversation, *, now: datetime | None = None) -> None:
    """Um Attendant escreveu na Conversation em Handoff: reinicia a contagem do timeout."""
    ticket_id = db.query(Conversation.ticket_id).filter(
        Conversation.id == conversation.id, Conversation.human_in_loop.is_(True)
    ).scalar()
    if not ticket_id:
        return
    db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.status.in_(OPEN_STATUSES)).update(
        {"attendant_activity_at": now or clock.utc_now()}, synchronize_session=False
    )
    db.commit()


# ---------- timeout ----------


def _last_touch(db: Session, conversation: Conversation) -> datetime | None:
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.ticket_id else None
    if ticket is not None:
        return _aware(max(t for t in (ticket.created_at, ticket.attendant_activity_at) if t is not None))
    stamp = conversation.updated_at or conversation.created_at  # Handoff antigo, sem Ticket
    return _aware(stamp) if stamp else None


def is_overdue(db: Session, conversation: Conversation, company: Company | None, now: datetime | None = None) -> bool:
    """True se a Conversation está em Handoff e nenhum Attendant agiu dentro do timeout da Company. Só lê."""
    if not conversation.human_in_loop or company is None:
        return False
    touched = _last_touch(db, conversation)
    if touched is None:
        return False
    timeout = timedelta(hours=company.handoff_timeout_hours or DEFAULT_TIMEOUT_HOURS)
    return (now or clock.utc_now()) - touched >= timeout


async def announce(instance: Instance | None, conversation: Conversation, change: str, ticket: Ticket | None) -> None:
    """Avisa a UI (`handoff_updated`). `change`: assumed | released | expired. Falha de notificação só loga (`publish_event`)."""
    if instance is None:
        return
    await publish_event(  # o estado já está gravado: falha de notificação só loga (`publish_event`)
        HandoffUpdated(
            instance_id=conversation.instance_id,
            conversation_id=conversation.id,
            change=change,
            human_in_loop=bool(conversation.human_in_loop),
            assigned_to=ticket.assigned_to if ticket and conversation.human_in_loop else None,
            ticket_id=ticket.id if ticket else None,
            timestamp=clock.utc_now(),
        )
    )


def _expire_if_due(
    db: Session, conversation: Conversation, instance: Instance, now: datetime | None
) -> Released | None:
    """Parte bloqueante de `expire_if_due` (roda em thread): julga o timeout e, vencido, devolve a Conversation.

    Depois do commit do `release`, atualiza `conversation` e `instance`: o `announce` os lê no event loop e um
    atributo expirado viraria um SELECT lá.
    """
    company = db.get(Company, instance.company_id) if instance.company_id else None
    if not is_overdue(db, conversation, company, now):
        return None
    released = release(db, conversation, status="expired", now=now, only_ticket_id=conversation.ticket_id)
    if released is not None:
        db.refresh(conversation)
        db.refresh(instance)
    return released


async def expire_if_due(db: Session, conversation: Conversation, instance: Instance, now: datetime | None = None) -> bool:
    """Devolve ao Agent uma Conversation cujo Handoff passou do timeout. True só se ESTA chamada devolveu.

    Se a API devolveu no meio, `release` não muda nada e nada é anunciado. O banco roda em thread; o aviso à UI, no loop.
    """
    released = await asyncio.to_thread(_expire_if_due, db, conversation, instance, now)
    if released is None:
        return False
    logger.info("Handoff expired, Conversation back to the Agent", conversation_id=conversation.id)
    await announce(instance, conversation, "expired", released.ticket)
    return True


def _handoff_rows(db: Session) -> list[tuple[Conversation, Instance]]:
    return (
        db.query(Conversation, Instance)
        .join(Instance, Instance.id == Conversation.instance_id)
        .filter(Conversation.human_in_loop.is_(True), Instance.company_id.isnot(None))
        .all()
    )


async def expire_overdue(db: Session, now: datetime | None = None) -> int:
    """Expira todos os Handoffs vencidos. Devolve quantos voltaram ao Agent."""
    rows = await asyncio.to_thread(_handoff_rows, db)
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
            await asyncio.to_thread(db.rollback)
            logger.exception("Handoff sweep failed")
        finally:
            await asyncio.to_thread(db.close)
        await asyncio.sleep(interval_seconds)
