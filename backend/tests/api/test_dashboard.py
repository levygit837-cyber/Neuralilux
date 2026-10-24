"""Dashboard: escopo por tenant, cada número contra a fixture conhecida e falha de banco como 5xx."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import structlog
from sqlalchemy import text

from app.models import Company, Instance, User
from app.services import dashboard_service as service
from tests.access_helpers import make_company, make_user, user_id
from tests.dashboard_helpers import ALICE_7D, _conversation, _instance, _message, seed_dashboard

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


def test_a_company_member_who_is_not_the_owner_sees_zeros(client, db, world):
    company_id = db.query(User).filter(User.email == "alice@example.com").one().company_id
    db.query(Instance).update({"company_id": company_id})
    db.commit()

    member = world["headers"]["sem_instancia"]  # mesma Company da Alice, mas dona de nada
    assert db.query(User).filter(User.email == "sem@example.com").one().company_id == company_id
    overview = client.get(f"{BASE}/overview", headers=member).json()

    assert overview["messages"] == {"current": 0, "previous": 0}
    assert overview["handoffs"] == {"current": 0, "previous": 0}
    assert client.get(f"{BASE}/messages-by-instance", headers=member).json() == {"instances": []}
    assert client.get(f"{BASE}/handoffs", headers=member).json() == {"open": 0, "in_progress": 0, "closed": 0, "expired": 0}


def test_an_inactive_instance_of_the_owner_is_out_of_scope(client, db, world):
    old = _instance(db, "Loja Antiga", user_id(db, "alice@example.com"))
    old.is_active = False
    when = datetime.now(timezone.utc) - timedelta(days=1)
    _message(db, _conversation(db, old, "antiga", when), when, "incoming")
    db.commit()

    assert get(client, world, "alice", "overview")["messages"]["current"] == ALICE_7D["messages"][0]
    chart = get(client, world, "alice", "messages-by-instance")
    assert "Loja Antiga" not in {i["name"] for i in chart["instances"]}


def test_the_user_zone_is_the_company_zone_and_decides_the_local_day(client, db, world):
    tokyo = Company(name="Tóquio", is_active=True, timezone="Asia/Tokyo")
    db.add(tokyo)
    db.flush()
    db.query(User).filter(User.email == "alice@example.com").update({"company_id": tokyo.id})
    db.commit()
    alice = db.query(User).filter(User.email == "alice@example.com").one()

    assert service.user_zone(db, alice) == ZoneInfo("Asia/Tokyo")
    assert get(client, world, "alice", "conversations-over-time")["timezone"] == "Asia/Tokyo"

    # 16:00 UTC de 23/10 já é 01:00 de 24/10 em Tóquio, mas ainda 13:00 de 23/10 em São Paulo
    now = datetime(2026, 10, 24, 2, 0, tzinfo=timezone.utc)
    instance = _instance(db, "Loja Tóquio", alice.id)
    _conversation(db, instance, "toquio", datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc))
    scope = [instance.id]
    in_tokyo = dict(service.conversations_per_day(db, scope, service.window_for("7d", ZoneInfo("Asia/Tokyo"), now)))
    in_sao_paulo = dict(service.conversations_per_day(db, scope, service.window_for("7d", ZoneInfo("America/Sao_Paulo"), now)))

    assert in_tokyo[datetime(2026, 10, 24).date()] == 1
    assert in_sao_paulo[datetime(2026, 10, 23).date()] == 1


def test_the_previous_period_ends_at_the_same_time_of_day_as_now(db):
    """Às 07:00 locais, o período atual tem 6 dias cheios + 7 horas; o anterior tem de ter o mesmo tamanho."""
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    now = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)  # 07:00 em São Paulo
    window = service.window_for("7d", sao_paulo, now)

    assert window.start == datetime(2026, 10, 18, 3, 0, tzinfo=timezone.utc)
    assert window.previous_start == datetime(2026, 10, 11, 3, 0, tzinfo=timezone.utc)
    assert window.previous_end == datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    assert window.previous_end - window.previous_start == now - window.start

    instance = _instance(db, "Loja Manhã", user_id_for(db))
    before_cut = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)  # 06:00 do dia 17: dentro do anterior
    after_cut = datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)  # 12:00 do dia 17: sem par no período atual
    for tag, at in (("antes", before_cut), ("depois", after_cut)):
        _message(db, _conversation(db, instance, tag, at), at, "incoming")
    db.commit()

    overview = service.overview(db, [instance.id], window)

    assert overview.messages.previous == 1
    assert overview.conversations.previous == 1
    assert overview.messages.current == 0


def user_id_for(db) -> str:
    user = User(email="manha@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    return user.id
