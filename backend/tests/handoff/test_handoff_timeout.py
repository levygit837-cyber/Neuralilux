"""Timeout do Handoff: sem atividade de Attendant dentro do prazo da Company, volta ao Agent e o Ticket expira."""
from datetime import timedelta

import pytest
from access_helpers import make_company, make_conversation, make_instance

from app.models import Conversation, Ticket
from app.services import handoff_service

pytestmark = pytest.mark.asyncio


def _handoff(db, *, timeout_hours=4, age_hours=0.0, activity_age_hours=None, tag="a"):
    company = make_company(db, f"Pizzaria {tag}")
    company.handoff_timeout_hours = timeout_hours
    db.commit()
    instance = make_instance(db, f"inst-timeout-{tag}", None, company=company)
    conversation = make_conversation(db, instance)
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
    now = handoff_service.utc_now()
    ticket.created_at = now - timedelta(hours=age_hours)
    if activity_age_hours is not None:
        ticket.attendant_activity_at = now - timedelta(hours=activity_age_hours)
    db.commit()
    return conversation, ticket, instance


async def test_handoff_without_attendant_expires_after_the_company_timeout(db, realtime):
    conversation, ticket, instance = _handoff(db, timeout_hours=4, age_hours=4.1)

    assert await handoff_service.expire_overdue(db) == 1

    db.expire_all()
    ticket = db.get(Ticket, ticket.id)
    assert ticket.status == "expired" and ticket.closed_at is not None
    conversation = db.get(Conversation, conversation.id)
    assert conversation.human_in_loop is False and conversation.ticket_id is None
    assert realtime[-1]["payload"]["change"] == "expired"


async def test_handoff_inside_the_timeout_is_left_alone(db, realtime):
    conversation, ticket, _ = _handoff(db, timeout_hours=4, age_hours=3.9)

    assert await handoff_service.expire_overdue(db) == 0

    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is True
    assert db.get(Ticket, ticket.id).status == "open" and realtime == []


async def test_timeout_is_configured_per_company(db, realtime):
    # Ambas com 2h de silêncio: vence para a Company de 1h, não para a de 4h.
    _, short_ticket, _ = _handoff(db, timeout_hours=1, age_hours=2, tag="curta")
    _, long_ticket, _ = _handoff(db, timeout_hours=4, age_hours=2, tag="longa")

    assert await handoff_service.expire_overdue(db) == 1

    db.expire_all()
    assert db.get(Ticket, short_ticket.id).status == "expired"
    assert db.get(Ticket, long_ticket.id).status == "open"


async def test_attendant_activity_restarts_the_timeout(db, realtime):
    conversation, ticket, _ = _handoff(db, timeout_hours=4, age_hours=10, activity_age_hours=1)

    assert await handoff_service.expire_overdue(db) == 0

    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is True


async def test_recording_attendant_activity_postpones_expiry(db, realtime):
    conversation, ticket, _ = _handoff(db, timeout_hours=4, age_hours=10)

    handoff_service.record_attendant_activity(db, conversation)

    assert await handoff_service.expire_overdue(db) == 0


async def test_conversation_without_handoff_is_never_expired(db, realtime):
    company = make_company(db, "Pizzaria")
    instance = make_instance(db, "inst-free", None, company=company)
    make_conversation(db, instance)

    assert await handoff_service.expire_overdue(db) == 0


async def test_expired_ticket_is_not_reopened_by_a_later_release(db, realtime):
    conversation, ticket, instance = _handoff(db, age_hours=5)
    await handoff_service.expire_if_due(db, conversation, instance)

    db.expire_all()
    assert handoff_service.release(db, db.get(Conversation, conversation.id)) is None
    assert db.get(Ticket, ticket.id).status == "expired"
