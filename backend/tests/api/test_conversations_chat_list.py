"""Lista de chats: categorias, contadores, leitura, sincronização e envio para grupo."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Contact, Conversation, Instance, Message
from app.whatsapp import history_sync
from app.whatsapp.evolution_client import EvolutionAPIError, evolution_api
from tests.access_helpers import make_instance, make_user


def _chat(db, instance, jid, name, *, is_group=False, unread=0, human=False, archived=False, preview=None):
    contact = Contact(instance_id=instance.id, phone_number=jid.split("@")[0][:20], remote_jid=jid, name=name)
    db.add(contact)
    db.flush()
    conversation = Conversation(
        instance_id=instance.id, contact_id=contact.id, remote_jid=jid, is_active=True, is_group=is_group,
        unread_count=unread, human_in_loop=human, is_archived=archived, last_message_preview=preview,
    )
    db.add(conversation)
    db.commit()
    return conversation


@pytest.fixture
def chats(client, db):
    headers = make_user(client, db, "dona@example.com")
    instance = make_instance(db, "inst-chats", "dona@example.com", agent_enabled=True)
    rows = {
        "bot": _chat(db, instance, "5511000000001@s.whatsapp.net", "Ana", preview="quero pizza"),
        "unread": _chat(db, instance, "5511000000002@s.whatsapp.net", "Bruno", unread=4),
        "human": _chat(db, instance, "5511000000003@s.whatsapp.net", "Carla", human=True, unread=1),
        "group": _chat(db, instance, "1-2@g.us", "Família", is_group=True, unread=2),
        "archived": _chat(db, instance, "5511000000004@s.whatsapp.net", "Dani", unread=9, archived=True),
    }
    return headers, instance, rows


def _ids(client, headers, instance, **params):
    response = client.get(
        "/api/v1/conversations", params={"instance_id": instance.id, "is_archived": False, **params}, headers=headers
    )
    assert response.status_code == 200
    return {item["id"] for item in response.json()["items"]}


def test_categories_filter_as_specified(client, chats):
    headers, instance, c = chats
    ids = lambda category: _ids(client, headers, instance, category=category)  # noqa: E731

    assert ids("all") == {c["bot"].id, c["unread"].id, c["human"].id, c["group"].id}
    assert ids("unread") == {c["unread"].id, c["human"].id, c["group"].id}
    assert ids("groups") == {c["group"].id}
    assert ids("human") == {c["human"].id}
    assert ids("ai") == {c["bot"].id, c["unread"].id}  # sem grupo e sem Handoff


def test_ai_category_is_empty_when_the_instance_agent_is_disabled(client, db, chats):
    headers, instance, _ = chats
    instance.agent_enabled = False
    db.commit()

    assert _ids(client, headers, instance, category="ai") == set()


def test_list_exposes_is_group_and_rejects_unknown_category(client, chats):
    headers, instance, c = chats
    items = client.get("/api/v1/conversations", params={"instance_id": instance.id, "category": "groups"}, headers=headers).json()["items"]
    assert [(i["id"], i["is_group"]) for i in items] == [(c["group"].id, True)]

    assert client.get("/api/v1/conversations", params={"category": "x"}, headers=headers).status_code == 422


def test_search_matches_name_and_last_message_without_duplicates(client, chats):
    headers, instance, c = chats
    c["bot"].last_message_preview = "Ana pediu pizza"  # nome e prévia casam: uma linha só
    client_response = client.get(
        "/api/v1/conversations", params={"instance_id": instance.id, "search": "ana"}, headers=headers
    ).json()
    assert [i["id"] for i in client_response["items"]] == [c["bot"].id] and client_response["total"] == 1

    assert _ids(client, headers, instance, search="pizza") == {c["bot"].id}


def test_counts_ignore_archived_and_badge_skips_group_unread(client, chats):
    headers, instance, _ = chats

    response = client.get("/api/v1/conversations/counts", params={"instance_id": instance.id}, headers=headers)

    assert response.status_code == 200
    # `unread_messages`: Bruno 4 + Carla 1; o grupo (2) e a arquivada (9) ficam fora do selo.
    assert response.json() == {"all": 4, "unread": 3, "groups": 1, "ai": 2, "human": 1, "unread_messages": 5}


def test_counts_require_instance_and_ownership(client, db, chats):
    headers, instance, _ = chats
    other = make_user(client, db, "outro@example.com")

    assert client.get("/api/v1/conversations/counts", headers=headers).status_code == 422
    assert client.get("/api/v1/conversations/counts", params={"instance_id": instance.id}, headers=other).status_code == 403


def test_read_zeroes_unread_and_checks_owner(client, db, chats):
    headers, _, c = chats
    other = make_user(client, db, "intruso@example.com")

    assert client.post(f"/api/v1/conversations/{c['unread'].id}/read", headers=other).status_code == 403
    assert client.post("/api/v1/conversations/nao-existe/read", headers=headers).status_code == 404

    response = client.post(f"/api/v1/conversations/{c['unread'].id}/read", headers=headers)
    assert response.status_code == 200 and response.json() == {"unread_count": 0}
    db.expire_all()
    assert db.get(Conversation, c["unread"].id).unread_count == 0


def test_sync_requires_a_connected_instance(client, db, chats):
    headers, instance, _ = chats

    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=headers)

    assert response.status_code == 400


def test_sync_returns_created_rows_and_maps_evolution_errors(client, db, chats, monkeypatch):
    headers, instance, _ = chats
    instance.status = "connected"
    db.commit()
    seen = []

    async def fake_ok(session, inst):
        seen.append(inst.id)
        return {"conversations": 2, "messages": 7}

    monkeypatch.setattr(history_sync, "sync_instance", fake_ok)
    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=headers)
    assert response.status_code == 200 and response.json() == {"conversations": 2, "messages": 7}
    assert seen == [instance.id]

    async def fake_error(session, inst):
        raise EvolutionAPIError("Evolution fora do ar", status_code=500)

    monkeypatch.setattr(history_sync, "sync_instance", fake_error)
    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=headers)
    assert response.status_code == 502


def test_sync_returns_409_when_another_process_is_importing(client, db, chats, monkeypatch):
    headers, instance, _ = chats
    instance.status = "connected"
    db.commit()

    async def busy(session, inst):
        raise history_sync.SyncAlreadyRunning(inst.id)

    monkeypatch.setattr(history_sync, "sync_instance", busy)

    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=headers)

    assert response.status_code == 409 and response.json()["detail"] == "Sincronização já em andamento"


def test_sync_returns_409_not_500_when_the_batch_keeps_conflicting(client, db, chats, monkeypatch):
    headers, instance, _ = chats
    instance.status = "connected"
    db.commit()

    async def conflicting(session, inst):
        raise IntegrityError("insert", {}, Exception("duplicate message_id"))

    monkeypatch.setattr(history_sync, "sync_instance", conflicting)

    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=headers)

    assert response.status_code == 409


def test_sync_of_another_users_instance_is_forbidden(client, db, chats):
    _, instance, _ = chats
    other = make_user(client, db, "alheio@example.com")

    response = client.post("/api/v1/conversations/sync", params={"instance_id": instance.id}, headers=other)

    assert response.status_code == 403


def test_sending_to_a_group_passes_the_full_jid(client, db, chats, monkeypatch):
    headers, instance, c = chats
    instance.status = "connected"
    db.commit()
    sent = []

    async def fake_post(self, method, endpoint, data=None, params=None, timeout=30.0):
        sent.append((endpoint, data))
        return {"key": {"id": "out-1"}}

    monkeypatch.setattr(type(evolution_api), "_request", fake_post)

    response = client.post(
        f"/api/v1/conversations/{c['group'].id}/messages", json={"content": "Oi grupo", "message_type": "text"}, headers=headers
    )

    assert response.status_code == 200
    [(endpoint, payload)] = sent
    assert endpoint == "/message/sendText/inst-chats" and payload["number"] == "1-2@g.us"
    db.expire_all()
    assert db.query(Message).filter(Message.conversation_id == c["group"].id).one().content == "Oi grupo"


@pytest.mark.asyncio
async def test_presence_and_text_use_full_group_jid_but_digits_for_people(monkeypatch):
    sent = []

    async def fake_post(self, method, endpoint, data=None, params=None, timeout=30.0):
        sent.append(data["number"])
        return {"key": {"id": "x"}}

    monkeypatch.setattr(type(evolution_api), "_request", fake_post)

    await evolution_api.send_text_message("inst", "553388773141-1562969789@g.us", "oi")
    await evolution_api.send_presence("inst", "553388773141-1562969789@g.us")
    await evolution_api.send_text_message("inst", "5511999990001@s.whatsapp.net", "oi")
    await evolution_api.send_presence("inst", "5511999990001@s.whatsapp.net")
    await evolution_api.send_text_message("inst", "98765@lid", "oi")  # @lid sem número real: nunca os dígitos
    await evolution_api.send_presence("inst", "98765@lid")

    assert sent == ["553388773141-1562969789@g.us"] * 2 + ["5511999990001"] * 2 + ["98765@lid"] * 2
