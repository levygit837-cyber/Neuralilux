"""Tickets restritos às Instances do usuário (T10)."""
import pytest

from tests.access_helpers import make_company, make_instance, make_ticket, make_user, user_id


@pytest.fixture
def world(client, db):
    company_a = make_company(db, "Empresa A")
    company_b = make_company(db, "Empresa B")
    alice = make_user(client, db, "alice@example.com", company=company_a)
    colega = make_user(client, db, "colega@example.com", company=company_a)
    bob = make_user(client, db, "bob@example.com", company=company_b)
    admin = make_user(client, db, "admin@example.com", superuser=True)
    ticket_a = make_ticket(db, make_instance(db, "inst-a", "alice@example.com", company_a))
    ticket_b = make_ticket(db, make_instance(db, "inst-b", "bob@example.com", company_b))
    return {
        "alice": alice, "colega": colega, "bob": bob, "admin": admin,
        "ticket_a": ticket_a.id, "ticket_b": ticket_b.id, "db": db,
    }


def test_list_is_filtered_per_user(client, world):
    alice = client.get("/api/v1/tickets/", headers=world["alice"]).json()
    assert [t["id"] for t in alice["tickets"]] == [world["ticket_a"]]
    assert alice["total"] == 1
    bob = client.get("/api/v1/tickets/", headers=world["bob"]).json()
    assert [t["id"] for t in bob["tickets"]] == [world["ticket_b"]]


def test_superuser_lists_all(client, world):
    body = client.get("/api/v1/tickets/", headers=world["admin"]).json()
    assert {t["id"] for t in body["tickets"]} == {world["ticket_a"], world["ticket_b"]}


def test_get_out_of_scope_ticket_is_404(client, world):
    assert client.get(f"/api/v1/tickets/{world['ticket_a']}", headers=world["alice"]).status_code == 200
    assert client.get(f"/api/v1/tickets/{world['ticket_a']}", headers=world["bob"]).status_code == 404
    assert client.get(f"/api/v1/tickets/{world['ticket_a']}", headers=world["admin"]).status_code == 200


def test_patch_out_of_scope_ticket_is_404_and_unchanged(client, world):
    response = client.patch(f"/api/v1/tickets/{world['ticket_a']}", params={"status": "closed"}, headers=world["bob"])
    assert response.status_code == 404
    assert client.get(f"/api/v1/tickets/{world['ticket_a']}", headers=world["alice"]).json()["status"] == "open"
    ok = client.patch(f"/api/v1/tickets/{world['ticket_a']}", params={"status": "closed"}, headers=world["alice"])
    assert ok.status_code == 200 and ok.json()["status"] == "closed"


def test_assign_out_of_scope_ticket_is_404(client, world):
    uid = user_id(world["db"], "colega@example.com")
    response = client.post(f"/api/v1/tickets/{world['ticket_a']}/assign", params={"user_id": uid}, headers=world["bob"])
    assert response.status_code == 404


def test_assign_accepts_user_of_the_instance_company(client, world):
    uid = user_id(world["db"], "colega@example.com")
    response = client.post(f"/api/v1/tickets/{world['ticket_a']}/assign", params={"user_id": uid}, headers=world["alice"])
    assert response.status_code == 200
    assert response.json()["assigned_to"] == uid
    assert response.json()["status"] == "in_progress"


def test_assign_refuses_user_of_another_company(client, world):
    bob_id = user_id(world["db"], "bob@example.com")
    response = client.post(f"/api/v1/tickets/{world['ticket_a']}/assign", params={"user_id": bob_id}, headers=world["alice"])
    assert response.status_code == 403
    assert client.get(f"/api/v1/tickets/{world['ticket_a']}", headers=world["alice"]).json()["assigned_to"] is None


def test_patch_assigned_to_applies_the_same_company_rule(client, world):
    bob_id = user_id(world["db"], "bob@example.com")
    response = client.patch(f"/api/v1/tickets/{world['ticket_a']}", params={"assigned_to": bob_id}, headers=world["alice"])
    assert response.status_code == 403


def test_superuser_may_assign_across_companies(client, world):
    bob_id = user_id(world["db"], "bob@example.com")
    response = client.post(f"/api/v1/tickets/{world['ticket_a']}/assign", params={"user_id": bob_id}, headers=world["admin"])
    assert response.status_code == 200


def test_assign_on_an_instance_without_company_is_refused_to_regular_users(client, db):
    dono = make_user(client, db, "dono@example.com")
    make_user(client, db, "outro@example.com")
    ticket = make_ticket(db, make_instance(db, "inst-sem-company", "dono@example.com"))

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/assign",
        params={"user_id": user_id(db, "outro@example.com")},
        headers=dono,
    )

    assert response.status_code == 403
    assert client.get(f"/api/v1/tickets/{ticket.id}", headers=dono).json()["assigned_to"] is None
