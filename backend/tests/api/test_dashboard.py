"""Dashboard: escopo por tenant, cada número contra a fixture conhecida e falha de banco como 5xx."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
import structlog
from sqlalchemy import text

from tests.access_helpers import make_company, make_user, user_id
from tests.dashboard_helpers import ALICE_7D, seed_dashboard

BASE = "/api/v1/dashboard"


@pytest.fixture
def world(client, db):
    company = make_company(db, "Empresa A")
    headers = {
        "alice": make_user(client, db, "alice@example.com", company=company),
        "bob": make_user(client, db, "bob@example.com"),
        "admin": make_user(client, db, "admin@example.com", superuser=True),
        "sem_instancia": make_user(client, db, "sem@example.com", company=company),
    }
    ids = seed_dashboard(
        db, datetime.now(timezone.utc), alice_id=user_id(db, "alice@example.com"), bob_id=user_id(db, "bob@example.com")
    )
    db.commit()
    return {"headers": headers, **ids}


def get(client, world, user: str, path: str, **params):
    response = client.get(f"{BASE}/{path}", params=params, headers=world["headers"][user])
    assert response.status_code == 200, response.text
    return response.json()


def test_overview_matches_the_known_fixture(client, world):
    body = get(client, world, "alice", "overview", period="7d")

    assert (body["conversations"]["current"], body["conversations"]["previous"]) == ALICE_7D["conversations"]
    assert (body["messages"]["current"], body["messages"]["previous"]) == ALICE_7D["messages"]
    assert (body["handoffs"]["current"], body["handoffs"]["previous"]) == ALICE_7D["handoffs"]
    rate = body["response_rate"]
    assert (rate["received"], rate["answered"]) == (ALICE_7D["received"], ALICE_7D["answered"])
    assert (rate["current"], rate["previous"]) == (ALICE_7D["response_rate"], ALICE_7D["previous_response_rate"])


def test_longer_period_moves_the_old_conversation_into_the_current_window(client, world):
    body = get(client, world, "alice", "overview", period="30d")

    assert body["conversations"] == {"current": 3, "previous": 0}
    assert body["handoffs"] == {"current": 3, "previous": 0}
    assert body["response_rate"]["received"] == 6  # 3 + 1 + 2 entradas; o grupo não conta


def test_response_rate_is_null_when_the_contact_did_not_write(client, world):
    body = get(client, world, "sem_instancia", "overview")

    assert body["response_rate"] == {"current": None, "previous": None, "received": 0, "answered": 0}
    assert body["conversations"] == {"current": 0, "previous": 0}


def test_users_see_only_their_own_instances(client, world):
    alice = get(client, world, "alice", "overview")
    bob = get(client, world, "bob", "overview")

    assert alice["messages"]["current"] == 7
    assert bob["messages"] == {"current": 1, "previous": 0}
    assert bob["handoffs"] == {"current": 1, "previous": 0}

    alice_chart = get(client, world, "alice", "messages-by-instance")
    bob_chart = get(client, world, "bob", "messages-by-instance")
    assert {i["instance_id"] for i in alice_chart["instances"]} == set(world["alice_instances"])
    assert {i["instance_id"] for i in bob_chart["instances"]} == set(world["bob_instances"])

    assert get(client, world, "bob", "handoffs") == {"open": 1, "in_progress": 0, "closed": 0, "expired": 0}
    assert sum(d["count"] for d in get(client, world, "bob", "conversations-over-time")["data"]) == 1


def test_superuser_sees_every_instance(client, world):
    body = get(client, world, "admin", "overview")

    assert body["conversations"]["current"] == 3  # Alice 2 + Bob 1
    assert body["messages"]["current"] == 8
    chart = get(client, world, "admin", "messages-by-instance")
    assert {i["name"] for i in chart["instances"]} == {"Loja Centro", "Loja Norte", "Loja do Bob"}


def test_messages_by_instance_uses_the_real_instance_name(client, world):
    body = get(client, world, "alice", "messages-by-instance", period="30d")

    assert [(i["name"], i["count"]) for i in body["instances"]] == [("Loja Centro", 7), ("Loja Norte", 3)]


def test_messages_by_instance_lists_a_quiet_instance_with_zero(client, world):
    body = get(client, world, "alice", "messages-by-instance", period="7d")

    assert [(i["name"], i["count"]) for i in body["instances"]] == [("Loja Centro", 7), ("Loja Norte", 0)]


def test_conversations_over_time_has_one_point_per_day_with_zeros(client, world):
    body = get(client, world, "alice", "conversations-over-time", period="7d")

    assert len(body["data"]) == 7
    by_day = {point["date"]: point["count"] for point in body["data"]}
    assert sum(by_day.values()) == 2
    c1_day = world["c1_created"].astimezone(ZoneInfo(body["timezone"])).date().isoformat()
    assert by_day[c1_day] == 1
    assert body["data"][-1]["count"] == 0
    assert [p["date"] for p in body["data"]] == sorted(p["date"] for p in body["data"])


def test_handoffs_are_counted_by_ticket_status(client, world):
    assert get(client, world, "alice", "handoffs", period="7d") == {"open": 1, "in_progress": 0, "closed": 1, "expired": 0}
    assert get(client, world, "alice", "handoffs", period="30d") == {"open": 1, "in_progress": 0, "closed": 1, "expired": 1}


def test_removed_made_up_endpoints_are_gone(client, world):
    for path in ("stats", "metrics", "channel-metrics", "resolution-metrics", "satisfaction-metrics"):
        assert client.get(f"{BASE}/{path}", headers=world["headers"]["alice"]).status_code == 404


def test_invalid_period_is_rejected(client, world):
    assert client.get(f"{BASE}/overview", params={"period": "1y"}, headers=world["headers"]["alice"]).status_code == 422


def test_requires_authentication(client):
    assert client.get(f"{BASE}/overview").status_code == 401


@pytest.mark.parametrize("path", ["overview", "handoffs"])
def test_database_failure_is_a_generic_500_with_a_traceback_in_the_log(client, db, world, path):
    db.commit()
    db.execute(text("DROP TABLE tickets"))  # falha real do banco, depois da autenticação

    with structlog.testing.capture_logs() as logs:
        response = client.get(f"{BASE}/{path}", headers=world["headers"]["alice"])

    assert response.status_code == 500
    assert response.json() == {"detail": "Erro ao carregar os dados do dashboard"}
    errors = [log for log in logs if log["event"] == "Error computing dashboard widget"]
    assert [(log["widget"], log["log_level"], bool(log["exc_info"])) for log in errors] == [(path, "error", True)]
