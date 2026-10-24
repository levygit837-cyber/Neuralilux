"""Leituras agregadas do dashboard. A definição de cada número está em `docs/dashboard.md`.

Todas as funções recebem `scope`: os ids das Instances que o usuário alcança (`instance_ids_for_user`; `None` é
o superusuário, sem filtro). Só entram Conversations 1:1 (grupos não são atendimento do Agent).

O período é "os últimos N dias, contando hoje", com os dias no fuso da Company. O período anterior são os N dias
imediatamente antes; é a base de comparação das tendências.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, case, exists, func, or_, true
from sqlalchemy.orm import Session, aliased

from app.agent.clock import DEFAULT_TIMEZONE, as_utc, company_zone
from app.models import Company, Conversation, Instance, Message, Ticket, User
from app.schemas.dashboard import CountMetric, DashboardOverview, ResponseRateMetric

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}
MAX_INSTANCES_IN_CHART = 10
TICKET_STATUSES = ("open", "in_progress", "closed", "expired")


def user_zone(db: Session, user: User) -> ZoneInfo:
    """Fuso da Company do usuário; sem Company (ex.: superusuário), o fuso padrão."""
    company = db.get(Company, user.company_id) if user.company_id else None
    return company_zone(company) if company else ZoneInfo(DEFAULT_TIMEZONE)


@dataclass(frozen=True)
class Window:
    zone: ZoneInfo
    days: int
    first_day: date  # primeiro dia local do período atual
    last_day: date  # hoje, no fuso da Company
    start: datetime  # UTC: início do primeiro dia local
    previous_start: datetime  # UTC: início do período anterior (termina em `start`)


def window_for(period: str, zone: ZoneInfo, now: datetime) -> Window:
    days = PERIOD_DAYS[period]
    last_day = now.astimezone(zone).date()
    first_day = last_day - timedelta(days=days - 1)

    def local_midnight(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)

    return Window(
        zone, days, first_day, last_day, local_midnight(first_day), local_midnight(first_day - timedelta(days=days))
    )


def _in_scope(column: ColumnElement, scope: list[str] | None) -> ColumnElement[bool]:
    return column.in_(scope) if scope is not None else true()


def _between(column: ColumnElement, start: datetime, end: datetime | None) -> list[ColumnElement[bool]]:
    conditions = [column >= start]
    if end is not None:
        conditions.append(column < end)
    return conditions


def new_conversations(db: Session, scope: list[str] | None, start: datetime, end: datetime | None = None) -> int:
    return db.query(func.count(Conversation.id)).filter(
        _in_scope(Conversation.instance_id, scope),
        Conversation.is_group.is_(False),
        *_between(Conversation.created_at, start, end),
    ).scalar()


def _messages(db: Session, scope: list[str] | None, start: datetime, end: datetime | None, *columns):
    return db.query(*columns).join(Conversation, Conversation.id == Message.conversation_id).filter(
        _in_scope(Message.instance_id, scope),
        Conversation.is_group.is_(False),
        *_between(Message.timestamp, start, end),
    )


def messages_count(db: Session, scope: list[str] | None, start: datetime, end: datetime | None = None) -> int:
    return _messages(db, scope, start, end, func.count(Message.id)).scalar()


def handoffs_count(db: Session, scope: list[str] | None, start: datetime, end: datetime | None = None) -> int:
    return db.query(func.count(Ticket.id)).filter(
        _in_scope(Ticket.instance_id, scope), *_between(Ticket.created_at, start, end)
    ).scalar()


def response_counts(
    db: Session, scope: list[str] | None, start: datetime, end: datetime | None = None
) -> tuple[int, int]:
    """(Messages do Contact no período, quantas delas têm uma Message de saída depois na mesma Conversation).

    Aviso do sistema (`sent_by="system"`) não é resposta.
    """
    reply = aliased(Message)
    answered = exists().where(
        reply.conversation_id == Message.conversation_id,
        reply.direction == "outgoing",
        reply.timestamp > Message.timestamp,
        or_(reply.sent_by.is_(None), reply.sent_by != "system"),
    )
    received, replied = _messages(
        db, scope, start, end, func.count(Message.id), func.count(case((answered, 1)))
    ).filter(Message.direction == "incoming").one()
    return received, replied


def percent(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def conversations_per_day(db: Session, scope: list[str] | None, window: Window) -> list[tuple[date, int]]:
    """Conversations novas por dia local, com os dias sem nenhuma em zero.

    Agrupa em Python, com o fuso da Company: o `GROUP BY` por data em SQL dependeria do dialeto e do fuso do banco.
    """
    created = db.query(Conversation.created_at).filter(
        _in_scope(Conversation.instance_id, scope),
        Conversation.is_group.is_(False),
        Conversation.created_at >= window.start,
    ).all()
    per_day = Counter(as_utc(row[0]).astimezone(window.zone).date() for row in created)
    return [
        (day, per_day.get(day, 0))
        for day in (window.first_day + timedelta(days=offset) for offset in range(window.days))
    ]


def messages_by_instance(
    db: Session, scope: list[str] | None, start: datetime
) -> list[tuple[str, str, int]]:
    """(id, nome, Messages no período) das Instances ativas do escopo, as mais movimentadas primeiro."""
    instances = db.query(Instance.id, Instance.name).filter(
        _in_scope(Instance.id, scope), Instance.is_active.is_(True)
    ).all()
    counts = dict(
        _messages(db, scope, start, None, Message.instance_id, func.count(Message.id))
        .group_by(Message.instance_id)
        .all()
    )
    ranked = sorted(((i.id, i.name, counts.get(i.id, 0)) for i in instances), key=lambda r: (-r[2], r[1], r[0]))
    return ranked[:MAX_INSTANCES_IN_CHART]


def handoffs_by_status(db: Session, scope: list[str] | None, start: datetime) -> dict[str, int]:
    rows = db.query(Ticket.status, func.count(Ticket.id)).filter(
        _in_scope(Ticket.instance_id, scope), Ticket.created_at >= start
    ).group_by(Ticket.status).all()
    by_status = dict(rows)
    return {status: by_status.get(status, 0) for status in TICKET_STATUSES}


def overview(db: Session, scope: list[str] | None, window: Window) -> DashboardOverview:
    """Os quatro cartões do topo, cada um com o valor do período e o do período anterior."""
    received, answered = response_counts(db, scope, window.start)
    previous_received, previous_answered = response_counts(db, scope, window.previous_start, window.start)
    return DashboardOverview(
        conversations=CountMetric(
            current=new_conversations(db, scope, window.start),
            previous=new_conversations(db, scope, window.previous_start, window.start),
        ),
        messages=CountMetric(
            current=messages_count(db, scope, window.start),
            previous=messages_count(db, scope, window.previous_start, window.start),
        ),
        handoffs=CountMetric(
            current=handoffs_count(db, scope, window.start),
            previous=handoffs_count(db, scope, window.previous_start, window.start),
        ),
        response_rate=ResponseRateMetric(
            current=percent(answered, received),
            previous=percent(previous_answered, previous_received),
            received=received,
            answered=answered,
        ),
    )
