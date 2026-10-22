"""Assumir e devolver pelo painel: estado, Ticket, listagem e eventos em tempo real."""
from access_helpers import make_company, make_conversation, make_instance, make_user, user_id

from app.models import Conversation, Ticket


def _setup(client, db, email="atendente@example.com"):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, email, company=company)
    instance = make_instance(db, f"inst-{email}", email, company=company)
    return headers, instance, make_conversation(db, instance)


def _listed(client, headers, instance_id):
    response = client.get("/api/v1/conversations", params={"instance_id": instance_id}, headers=headers)
    return {c["id"]: c for c in response.json()["items"]}


def test_take_control_opens_ticket_assigned_to_the_attendant(client, db, realtime):
    headers, instance, conversation = _setup(client, db)

    response = client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["human_in_loop"] is True
    assert body["assigned_to"] == user_id(db, "atendente@example.com")
    ticket = db.query(Ticket).one()
    assert (ticket.status, ticket.assigned_to) == ("in_progress", body["assigned_to"])
    assert ticket.attendant_activity_at is not None
    assert [e["type"] for e in realtime] == ["handoff_updated"]
    assert realtime[0]["payload"]["change"] == "assumed"
    assert realtime[0]["payload"]["human_in_loop"] is True


def test_take_control_on_agent_requested_handoff_assigns_the_same_ticket(client, db, realtime):
    headers, instance, conversation = _setup(client, db)
    ticket = Ticket(
        conversation_id=conversation.id, instance_id=instance.id, contact_id=conversation.contact_id,
        agent_type="whatsapp_agent", reason="Pedido veio errado", content="x", status="open",
    )
    db.add(ticket)
    db.flush()
    conversation.human_in_loop = True
    conversation.ticket_id = ticket.id
    db.commit()

    client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)

    db.expire_all()
    assert db.query(Ticket).count() == 1
    ticket = db.query(Ticket).one()
    assert ticket.status == "in_progress" and ticket.assigned_to == user_id(db, "atendente@example.com")


def test_release_control_closes_ticket_and_returns_to_agent(client, db, realtime):
    headers, instance, conversation = _setup(client, db)
    client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)

    response = client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)

    assert response.status_code == 200 and response.json()["human_in_loop"] is False
    db.expire_all()
    ticket = db.query(Ticket).one()
    assert ticket.status == "closed" and ticket.closed_at is not None
    conversation = db.get(Conversation, conversation.id)
    assert conversation.human_in_loop is False and conversation.ticket_id is None
    assert realtime[-1]["payload"]["change"] == "released"
    assert realtime[-1]["payload"]["human_in_loop"] is False


def test_release_without_handoff_changes_nothing(client, db, realtime):
    headers, instance, conversation = _setup(client, db)

    response = client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)

    assert response.status_code == 200 and response.json()["human_in_loop"] is False
    assert realtime == [] and db.query(Ticket).count() == 0


def test_state_survives_reload_through_the_listing(client, db, realtime):
    headers, instance, conversation = _setup(client, db)
    client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)

    item = _listed(client, headers, instance.id)[conversation.id]
    assert item["human_in_loop"] is True
    assert item["handoff_assigned_to"] == user_id(db, "atendente@example.com")

    client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)
    item = _listed(client, headers, instance.id)[conversation.id]
    assert item["human_in_loop"] is False and item["handoff_assigned_to"] is None


def test_other_users_cannot_take_or_release(client, db, realtime):
    _headers, _instance, conversation = _setup(client, db)
    intruder = make_user(client, db, "intruso@example.com", company=make_company(db, "Outra"))

    assert client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=intruder).status_code == 403
    assert client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=intruder).status_code == 403
    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is False
