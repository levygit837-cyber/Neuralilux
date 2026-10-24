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


def test_ticket_mutation_routes_are_gone(client, world):
    """Assumir e devolver só existem nas rotas de controle humano da Conversation."""
    url = f"/api/v1/tickets/{world['ticket_a']}"
    uid = user_id(world["db"], "colega@example.com")

    patch = client.patch(url, params={"status": "closed"}, headers=world["alice"])
    patch_body = client.patch(url, json={"status": "closed"}, headers=world["alice"])
    assign = client.post(f"{url}/assign", params={"user_id": uid}, headers=world["alice"])

    assert (patch.status_code, patch_body.status_code) == (405, 405)  # a rota /tickets/{id} só aceita GET
    assert assign.status_code == 404  # /tickets/{id}/assign não existe
    ticket = client.get(url, headers=world["alice"]).json()
    assert (ticket["status"], ticket["assigned_to"]) == ("open", None)
