"""O painel anuncia o Handoff no event bus real; se o bus cair, o estado já gravado vale e a API responde 200."""

import pytest

from app.models import Conversation
from app.realtime.event_bus import realtime_event_bus
from tests.access_helpers import make_company, make_conversation, make_instance, make_user


@pytest.fixture
def setup(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "atendente@example.com", company=company)
    instance = make_instance(db, "inst-bus", "atendente@example.com", company=company)
    return headers, instance, make_conversation(db, instance)


def test_take_and_release_publish_handoff_updated_on_the_event_bus(client, setup, monkeypatch):
    headers, instance, conversation = setup
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(realtime_event_bus, "publish", capture)

    client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)
    client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)

    assert [(e["type"], e["payload"]["change"]) for e in published] == [
        ("handoff_updated", "assumed"),
        ("handoff_updated", "released"),
    ]
    assert {e["instance_name"] for e in published} == {instance.name}
    assert [e["payload"]["human_in_loop"] for e in published] == [True, False]


def test_event_bus_failure_does_not_undo_the_release(client, db, setup, monkeypatch):
    headers, _instance, conversation = setup
    client.post(f"/api/v1/conversations/{conversation.id}/take-control", json={}, headers=headers)

    async def boom(event):
        raise ConnectionError("redis fora do ar")

    monkeypatch.setattr(realtime_event_bus, "publish", boom)

    response = client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)

    assert response.status_code == 200 and response.json()["human_in_loop"] is False
    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is False
