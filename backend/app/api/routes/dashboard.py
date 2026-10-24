"""Dashboard: números do atendimento nas Instances do usuário. Definições em `docs/dashboard.md`.

Falha de banco não vira zero: `logger.exception` registra o traceback e a resposta é um 500 genérico, que o
frontend mostra no widget que falhou.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.dashboard import (
    ConversationsOverTime,
    ConversationsPerDay,
    DashboardOverview,
    HandoffsByStatus,
    InstanceMessages,
    MessagesByInstance,
)
from app.services import dashboard_service as service

logger = structlog.get_logger()

router = APIRouter()

PeriodParam = Query("7d", description="Últimos N dias, contando hoje (fuso da Company)")
Period = Literal["7d", "30d", "90d"]


@contextmanager
def _database_errors(widget: str) -> Iterator[None]:
    try:
        yield
    except SQLAlchemyError:
        logger.exception("Error computing dashboard widget", widget=widget)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao carregar os dados do dashboard"
        )


def _window(db: Session, user: User, period: str) -> service.Window:
    return service.window_for(period, service.user_zone(db, user), datetime.now(timezone.utc))


@router.get("/overview", response_model=DashboardOverview)
def get_overview(
    period: Period = PeriodParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conversas novas, Messages, Handoffs e taxa de resposta do período, cada um contra o período anterior."""
    with _database_errors("overview"):
        scope = instance_ids_for_user(db, current_user)
        return service.overview(db, scope, _window(db, current_user, period))


@router.get("/conversations-over-time", response_model=ConversationsOverTime)
def get_conversations_over_time(
    period: Period = PeriodParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conversas novas por dia local, com os dias sem nenhuma em zero."""
    with _database_errors("conversations-over-time"):
        scope = instance_ids_for_user(db, current_user)
        window = _window(db, current_user, period)
        days = service.conversations_per_day(db, scope, window)
        return ConversationsOverTime(
            timezone=window.zone.key,
            data=[ConversationsPerDay(date=day.isoformat(), count=count) for day, count in days],
        )


@router.get("/messages-by-instance", response_model=MessagesByInstance)
def get_messages_by_instance(
    period: Period = PeriodParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Messages do período por Instance, com o nome real dela."""
    with _database_errors("messages-by-instance"):
        scope = instance_ids_for_user(db, current_user)
        window = _window(db, current_user, period)
        rows = service.messages_by_instance(db, scope, window.start)
        return MessagesByInstance(
            instances=[InstanceMessages(instance_id=i, name=name, count=count) for i, name, count in rows]
        )


@router.get("/handoffs", response_model=HandoffsByStatus)
def get_handoffs(
    period: Period = PeriodParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tickets abertos no período, por status."""
    with _database_errors("handoffs"):
        scope = instance_ids_for_user(db, current_user)
        window = _window(db, current_user, period)
        return HandoffsByStatus(**service.handoffs_by_status(db, scope, window.start))
