"""Timeout do Handoff: sem atividade de Attendant dentro do prazo da Company, volta ao Agent e o Ticket expira.

O relógio é injetado (`now=`): nenhum teste depende da hora real.
"""
from datetime import datetime, timedelta, timezone

import pytest
from access_helpers import make_company, make_conversation, make_instance

from app.models import Conversation, Ticket
from app.services import handoff_service
from tests.conftest import TestingSessionLocal

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)


def _handoff(db, *, timeout_hours=4, age_hours=0.0, activity_age_hours=None, tag="a"):
    company = make_company(db, f"Pizzaria {tag}")
    company.handoff_timeout_hours = timeout_hours
    db.commit()
    instance = make_instance(db, f"inst-timeout-{tag}", None, company=company)
    conversation = make_conversation(db, instance)
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação", now=NOW)
    ticket.created_at = NOW - timedelta(hours=age_hours)
    if activity_age_hours is not None:
        ticket.attendant_activity_at = NOW - timedelta(hours=activity_age_hours)
    db.commit()
    return conversation, ticket, instance


async def test_handoff_without_attendant_expires_after_the_company_timeout(db, realtime):
    conversation, ticket, _ = _handoff(db, timeout_hours=4, age_hours=4.1)

    assert await handoff_service.expire_overdue(db, now=NOW) == 1

    db.expire_all()
    ticket = db.get(Ticket, ticket.id)
    assert ticket.status == "expired" and ticket.closed_at is not None
    conversation = db.get(Conversation, conversation.id)
    assert conversation.human_in_loop is False and conversation.ticket_id is None
    assert realtime[-1]["payload"]["change"] == "expired"


async def test_handoff_inside_the_timeout_is_left_alone(db, realtime):
    conversation, ticket, _ = _handoff(db, timeout_hours=4, age_hours=3.9)

    assert await handoff_service.expire_overdue(db, now=NOW) == 0

    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is True
    assert db.get(Ticket, ticket.id).status == "open" and realtime == []


async def test_timeout_is_configured_per_company(db, realtime):
    # Ambas com 2h de silêncio: vence para a Company de 1h, não para a de 4h.
    _, short_ticket, _ = _handoff(db, timeout_hours=1, age_hours=2, tag="curta")
    _, long_ticket, _ = _handoff(db, timeout_hours=4, age_hours=2, tag="longa")

    assert await handoff_service.expire_overdue(db, now=NOW) == 1

    db.expire_all()
    assert db.get(Ticket, short_ticket.id).status == "expired"
    assert db.get(Ticket, long_ticket.id).status == "open"


async def test_attendant_activity_restarts_the_timeout(db, realtime):
    conversation, _, _ = _handoff(db, timeout_hours=4, age_hours=10, activity_age_hours=1)

    assert await handoff_service.expire_overdue(db, now=NOW) == 0

    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is True


async def test_recording_attendant_activity_postpones_expiry(db, realtime):
    conversation, _, _ = _handoff(db, timeout_hours=4, age_hours=10)

    handoff_service.record_attendant_activity(db, conversation, now=NOW)

    assert await handoff_service.expire_overdue(db, now=NOW) == 0
    assert await handoff_service.expire_overdue(db, now=NOW + timedelta(hours=4, minutes=1)) == 1


async def test_conversation_without_handoff_is_never_expired(db, realtime):
    company = make_company(db, "Pizzaria")
    instance = make_instance(db, "inst-free", None, company=company)
    make_conversation(db, instance)

    assert await handoff_service.expire_overdue(db, now=NOW) == 0


async def test_released_ticket_cannot_become_expired_afterwards(db, realtime):
    conversation, ticket, instance = _handoff(db, age_hours=5)
    handoff_service.release(db, conversation, now=NOW)

    assert await handoff_service.expire_if_due(db, conversation, instance, now=NOW) is False

    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "closed"
    assert handoff_service.release(db, db.get(Conversation, conversation.id), now=NOW) is None


async def test_release_racing_the_sweeper_makes_a_single_transition(db, realtime):
    """O sweeper leu o Handoff como vencido; antes de ele escrever, a API devolve. Só a API anuncia."""
    conversation, ticket, instance = _handoff(db, age_hours=5)
    sweeper_db = TestingSessionLocal()
    try:
        stale_conversation = sweeper_db.get(Conversation, conversation.id)
        stale_instance = sweeper_db.get(type(instance), instance.id)
        assert stale_conversation.human_in_loop is True  # a visão do sweeper antes da devolução

        released = handoff_service.release(db, conversation, now=NOW)
        await handoff_service.announce(instance, conversation, "released", released.ticket)

        expired = await handoff_service.expire_if_due(sweeper_db, stale_conversation, stale_instance, now=NOW)
    finally:
        sweeper_db.close()

    assert released is not None and expired is False
    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "closed"
    assert [e["payload"]["change"] for e in realtime] == ["released"]


async def test_expire_racing_a_release_makes_a_single_transition(db, realtime):
    """Ordem inversa: o timeout vence primeiro; a devolução da API que chega depois não muda nem anuncia nada."""
    conversation, ticket, instance = _handoff(db, age_hours=5)
    api_db = TestingSessionLocal()
    try:
        api_conversation = api_db.get(Conversation, conversation.id)
        assert api_conversation.human_in_loop is True

        assert await handoff_service.expire_if_due(db, conversation, instance, now=NOW) is True
        late = handoff_service.release(api_db, api_conversation, now=NOW)
    finally:
        api_db.close()

    assert late is None
    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "expired"
    assert [e["payload"]["change"] for e in realtime] == ["expired"]


async def test_new_handoff_after_the_judged_one_ended_is_not_expired(db, realtime):
    """O sweeper julgou o Ticket A vencido; A foi devolvido e o Agent abriu o Ticket B (novo) antes da escrita."""
    conversation, old_ticket, instance = _handoff(db, age_hours=5)
    sweeper_db = TestingSessionLocal()
    try:
        stale_conversation = sweeper_db.get(Conversation, conversation.id)
        stale_instance = sweeper_db.get(type(instance), instance.id)
        assert stale_conversation.ticket_id == old_ticket.id

        handoff_service.release(db, conversation, now=NOW)
        fresh = handoff_service.open_handoff(db, conversation, "Outra reclamação", now=NOW)
        fresh.created_at = NOW
        db.commit()

        expired = await handoff_service.expire_if_due(sweeper_db, stale_conversation, stale_instance, now=NOW)
    finally:
        sweeper_db.close()

    assert expired is False
    db.expire_all()
    assert db.get(Conversation, conversation.id).ticket_id == fresh.id
    assert db.get(Ticket, fresh.id).status == "open"
