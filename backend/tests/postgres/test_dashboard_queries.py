"""Dashboard no Postgres migrado: as mesmas contas da fixture conhecida, mais a virada de dia no fuso da Company."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import User
from app.services import dashboard_service as service
from tests.dashboard_helpers import ALICE_7D, _conversation, _instance, seed_dashboard

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc)
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def seeded(pg):
    alice = User(email="alice@example.com", hashed_password="x")
    bob = User(email="bob@example.com", hashed_password="x")
    pg.add_all([alice, bob])
    pg.flush()
    ids = seed_dashboard(pg, NOW, alice_id=alice.id, bob_id=bob.id)
    return {"scope": ids["alice_instances"], "bob_scope": ids["bob_instances"], "pg": pg}


def test_overview_matches_the_known_fixture(seeded):
    window = service.window_for("7d", SAO_PAULO, NOW)

    result = service.overview(seeded["pg"], seeded["scope"], window)

    assert (result.conversations.current, result.conversations.previous) == ALICE_7D["conversations"]
    assert (result.messages.current, result.messages.previous) == ALICE_7D["messages"]
    assert (result.handoffs.current, result.handoffs.previous) == ALICE_7D["handoffs"]
    rate = result.response_rate
    assert (rate.received, rate.answered, rate.current, rate.previous) == (
        ALICE_7D["received"], ALICE_7D["answered"], ALICE_7D["response_rate"], ALICE_7D["previous_response_rate"],
    )


def test_scope_none_is_every_instance_and_a_list_is_only_its_own(seeded):
    window = service.window_for("7d", SAO_PAULO, NOW)

    everyone = service.overview(seeded["pg"], None, window)
    bob = service.overview(seeded["pg"], seeded["bob_scope"], window)

    assert everyone.conversations.current == 3
    assert (bob.conversations.current, bob.messages.current, bob.handoffs.current) == (1, 1, 1)


def test_conversations_per_day_buckets_by_the_company_local_day(pg):
    """02:30 UTC de 24/10 ainda é 23/10 em São Paulo (UTC-3); em UTC seria outro dia."""
    owner = User(email="dia@example.com", hashed_password="x")
    pg.add(owner)
    pg.flush()
    instance = _instance(pg, "Loja Dia", owner.id)
    _conversation(pg, instance, "a", datetime(2026, 10, 24, 2, 30, tzinfo=timezone.utc))
    _conversation(pg, instance, "b", datetime(2026, 10, 24, 3, 30, tzinfo=timezone.utc))
    _conversation(pg, instance, "c", datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc))
    window = service.window_for("7d", SAO_PAULO, NOW)

    days = dict(service.conversations_per_day(pg, [instance.id], window))

    assert len(days) == 7
    assert days[date(2026, 10, 24)] == 1
    assert days[date(2026, 10, 23)] == 1
    assert days[date(2026, 10, 22)] == 1
    assert days[date(2026, 10, 21)] == 0


def test_period_start_is_local_midnight_not_a_rolling_24h(seeded):
    window = service.window_for("7d", SAO_PAULO, NOW)

    assert window.first_day == date(2026, 10, 18)
    assert window.start == datetime(2026, 10, 18, 3, 0, tzinfo=timezone.utc)
    assert window.previous_start == datetime(2026, 10, 11, 3, 0, tzinfo=timezone.utc)


def test_messages_by_instance_and_handoffs_by_status(seeded):
    pg = seeded["pg"]
    start = service.window_for("30d", SAO_PAULO, NOW).start

    chart = service.messages_by_instance(pg, seeded["scope"], start)
    handoffs = service.handoffs_by_status(pg, seeded["scope"], start)

    assert [(name, count) for _, name, count in chart] == [("Loja Centro", 7), ("Loja Norte", 3)]
    assert handoffs == {"open": 1, "in_progress": 0, "closed": 1, "expired": 1}
