"""A listagem de Conversations expõe `human_in_loop` para a UI manter o badge de Handoff."""
from tests.access_helpers import make_conversation, make_instance, make_user


def _conversations(client, headers, instance_id):
    response = client.get("/api/v1/conversations", params={"instance_id": instance_id}, headers=headers)
    assert response.status_code == 200
    return {c["id"]: c for c in response.json()["items"]}


def test_list_reflects_human_in_loop_flag(client, db):
    headers = make_user(client, db, "dona@example.com")
    instance = make_instance(db, "inst-handoff", "dona@example.com")
    bot = make_conversation(db, instance)
    humana = make_conversation(db, instance)
    humana.human_in_loop = True
    db.commit()

    items = _conversations(client, headers, instance.id)
    assert items[bot.id]["human_in_loop"] is False
    assert items[humana.id]["human_in_loop"] is True


def test_release_control_clears_flag_in_list(client, db):
    headers = make_user(client, db, "dona2@example.com")
    instance = make_instance(db, "inst-release", "dona2@example.com")
    conversation = make_conversation(db, instance)
    conversation.human_in_loop = True
    db.commit()
    assert _conversations(client, headers, instance.id)[conversation.id]["human_in_loop"] is True

    response = client.post(f"/api/v1/conversations/{conversation.id}/release-control", headers=headers)
    assert response.status_code == 200

    assert _conversations(client, headers, instance.id)[conversation.id]["human_in_loop"] is False
