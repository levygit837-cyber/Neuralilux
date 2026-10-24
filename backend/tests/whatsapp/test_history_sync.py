"""Importação do histórico da Evolution: chats 1:1, @lid, grupos, nomes, dedup e contadores."""
from datetime import datetime, timezone

import asyncio
from types import SimpleNamespace

import pytest

from app.models import Contact, Conversation, Message
from app.whatsapp import history_sync
from app.whatsapp.evolution_client import evolution_api
from tests.conftest import TestingSessionLocal

PHONE = "5511999990001@s.whatsapp.net"
LID = "98765@lid"
GROUP = "553388773141-1562969789@g.us"
T0 = 1_760_000_000


def _record(message_id, jid, text, ts, *, from_me=False, push_name=None, participant=None, alt=None, message=None):
    key = {"id": message_id, "fromMe": from_me, "remoteJid": jid}
    if participant:
        key["participant"] = participant
    if alt:
        key["remoteJidAlt"] = alt
    return {
        "key": key,
        "pushName": push_name,
        "message": message if message is not None else {"conversation": text},
        "messageType": "conversation",
        "messageTimestamp": ts,
    }


@pytest.fixture
def evolution(monkeypatch, world):
    """Evolution falsa: o que cada chamada devolve é configurável, e o número de páginas lidas é registrado."""
    data = {
        "pages": [
            [  # página 1: as mais novas
                _record("m5", GROUP, "Alguém viu?", T0 + 50, push_name="João", participant="111@lid"),
                _record("m4", LID, "Resposta pelo lid", T0 + 40, from_me=True, push_name="Meu Número", alt=PHONE),
                _record("m3", PHONE, "Quero uma pizza", T0 + 30, push_name="Ana", alt=None),
                _record("x1", GROUP, "", T0 + 45, message={"reactionMessage": {"text": "👍"}}),
            ],
            [  # página 2: as mais antigas
                _record("m2", LID, "Oi, tudo bem?", T0 + 20, push_name="Ana", alt=PHONE),
                _record("m1", "status@broadcast", "story", T0 + 10, push_name="Fulano"),
                _record("m0", "5511888880002@lid", "Sem par", T0, push_name="Sem Par"),
            ],
        ],
        "chats": [
            {"remoteJid": PHONE, "pushName": None, "unreadCount": 3},
            {"remoteJid": GROUP, "pushName": "Nome do chat", "unreadCount": None},
            {"remoteJid": "5511888880002@lid", "pushName": None, "unreadCount": 0},
        ],
        "groups": [{"id": GROUP, "subject": "Família Macedo"}],
        "contacts": [{"remoteJid": PHONE, "pushName": "Ana (agenda)"}],
        "pages_read": [],
    }

    async def find_chats(name):
        return data["chats"]

    async def find_contacts(name):
        return data["contacts"]

    async def fetch_all_groups(name):
        return data["groups"]

    async def find_messages_page(name, page):
        data["pages_read"].append(page)
        return data["pages"][page - 1], len(data["pages"])

    monkeypatch.setattr(evolution_api, "fetch_chats", find_chats)
    monkeypatch.setattr(evolution_api, "fetch_contacts", find_contacts)
    monkeypatch.setattr(evolution_api, "fetch_groups", fetch_all_groups)
    monkeypatch.setattr(evolution_api, "fetch_messages_page", find_messages_page)
    return data


def _by_jid(db):
    db.expire_all()
    return {c.remote_jid: c for c in db.query(Conversation).all()}


@pytest.mark.asyncio
async def test_sync_imports_one_to_one_lid_and_group_with_names(db, world, evolution):
    result = await history_sync.sync_instance(db, world["instance"])

    # 4 chats com mensagem visível: PHONE (via @lid + direto), GROUP, @lid sem par. broadcast e reação ficam fora.
    assert result == {"conversations": 3, "messages": 5}
    conversations = _by_jid(db)
    assert set(conversations) == {PHONE, GROUP, "5511888880002@lid"}
    assert conversations[GROUP].is_group is True
    assert conversations[PHONE].is_group is False

    names = {c.remote_jid: c.name for c in db.query(Contact).all()}
    assert names[GROUP] == "Família Macedo"
    assert names[PHONE] == "Ana"  # pushName de Message recebida; o de `fromMe` ("Meu Número") nunca nomeia
    assert names["5511888880002@lid"] == "Sem Par"
    assert "Meu Número" not in names.values()
    assert evolution["pages_read"] == [1, 2, 1, 2]  # uma passada aprende @lid e pushNames, a outra grava


@pytest.mark.asyncio
async def test_sync_writes_page_by_page_without_holding_the_whole_history(db, world, evolution, monkeypatch):
    """Quando a página 2 é lida na passada de escrita, as Messages da página 1 já estão confirmadas."""
    real_page = evolution_api.fetch_messages_page
    stored_at_fetch = []

    async def watching_page(name, page):
        other = TestingSessionLocal()
        try:
            stored_at_fetch.append((page, other.query(Message).count()))
        finally:
            other.close()
        return await real_page(name, page)

    monkeypatch.setattr(evolution_api, "fetch_messages_page", watching_page)

    await history_sync.sync_instance(db, world["instance"])

    # Passada 1 (1, 2): nada gravado. Passada 2: a página 1 tem 3 Messages visíveis (m3, m4, m5) gravadas antes da 2.
    assert stored_at_fetch == [(1, 0), (2, 0), (1, 0), (2, 3)]


def test_unread_is_applied_without_reading_each_conversation(db, world):
    from sqlalchemy import event

    from app.models import Instance

    instance = db.get(Instance, world["instance"].id)
    created, chats = {}, []
    for n in range(30):
        jid = f"55119999{n:05d}@s.whatsapp.net"
        contact = Contact(instance_id=instance.id, phone_number=str(n), remote_jid=jid, name=str(n))
        db.add(contact)
        db.flush()
        conversation = Conversation(instance_id=instance.id, contact_id=contact.id, remote_jid=jid)
        db.add(conversation)
        db.flush()
        created[jid] = conversation.id
        chats.append({"remoteJid": jid, "unreadCount": n})
    db.commit()

    statements = []
    engine = db.get_bind()
    listener = lambda conn, cursor, statement, *rest: statements.append(statement)  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        history_sync._apply_unread(db, created, chats, lambda jid: jid)
        db.commit()
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    assert not [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    db.expire_all()
    assert {c.remote_jid: c.unread_count for c in db.query(Conversation).all()} == {
        chat["remoteJid"]: chat["unreadCount"] for chat in chats
    }


@pytest.mark.asyncio
async def test_sync_stores_direction_sender_timestamp_and_status(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])

    db.expire_all()
    stored = {m.message_id: m for m in db.query(Message).all()}
    assert set(stored) == {"m0", "m2", "m3", "m4", "m5"}  # sem broadcast nem reação
    assert (stored["m4"].is_from_me, stored["m4"].direction, stored["m4"].remote_jid) == (True, "outgoing", PHONE)
    assert (stored["m3"].is_from_me, stored["m3"].direction, stored["m3"].status) == (False, "incoming", "sent")
    assert stored["m5"].sender_name == "João"
    assert stored["m3"].sender_name is None
    assert stored["m3"].timestamp.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(T0 + 30, tz=timezone.utc)


@pytest.mark.asyncio
async def test_sync_sets_last_message_and_unread_from_find_chats(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])

    conversations = _by_jid(db)
    phone, group = conversations[PHONE], conversations[GROUP]
    assert phone.last_message_preview == "Resposta pelo lid"  # m4 é a mais nova do chat
    assert phone.last_message_at.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(T0 + 40, tz=timezone.utc)
    assert phone.unread_count == 3
    assert group.unread_count == 0  # unreadCount null: fica como estava
    assert group.last_message_preview == "Alguém viu?"


@pytest.mark.asyncio
async def test_second_run_creates_nothing_and_keeps_existing_rows(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])
    db.query(Message).filter(Message.message_id == "m3").update({"content": "editado localmente"})
    db.commit()

    again = await history_sync.sync_instance(db, world["instance"])

    assert again == {"conversations": 0, "messages": 0}
    assert db.query(Message).count() == 5 and db.query(Conversation).count() == 3
    assert db.query(Message).filter(Message.message_id == "m3").one().content == "editado localmente"


@pytest.mark.asyncio
async def test_sync_never_calls_the_agent_or_rolls_a_session(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])

    assert world["turns"] == [] and world["sent"] == []
    assert all(c.session_started_at is None for c in db.query(Conversation).all())


@pytest.mark.asyncio
async def test_sync_does_not_move_last_message_backwards(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])
    group = _by_jid(db)[GROUP]
    newer = datetime.fromtimestamp(T0 + 9999, tz=timezone.utc)
    group.last_message_at, group.last_message_preview = newer, "mensagem ao vivo"
    db.add(Message(
        instance_id=world["instance"].id, conversation_id=group.id, remote_jid=GROUP, message_id="m6",
        direction="incoming", timestamp=newer, content="mensagem ao vivo",
    ))
    db.commit()

    await history_sync.sync_instance(db, world["instance"])

    assert _by_jid(db)[GROUP].last_message_preview == "mensagem ao vivo"


@pytest.mark.asyncio
async def test_sync_survives_groups_and_contacts_failing(db, world, evolution, monkeypatch):
    from app.whatsapp.evolution_client import EvolutionAPIError

    async def boom(name):
        raise EvolutionAPIError("fora", status_code=500)

    monkeypatch.setattr(evolution_api, "fetch_groups", boom)
    monkeypatch.setattr(evolution_api, "fetch_contacts", boom)

    result = await history_sync.sync_instance(db, world["instance"])

    assert result["messages"] == 5
    assert {c.remote_jid: c.name for c in db.query(Contact).all()}[GROUP] == "Nome do chat"


@pytest.mark.asyncio
async def test_resync_does_not_overwrite_unread_of_existing_conversations(db, world, evolution):
    await history_sync.sync_instance(db, world["instance"])
    phone = _by_jid(db)[PHONE]
    phone.unread_count = 0  # o atendente abriu o chat (`/read`)
    db.commit()
    evolution["chats"][0]["unreadCount"] = 8

    await history_sync.sync_instance(db, world["instance"])

    assert _by_jid(db)[PHONE].unread_count == 0


@pytest.mark.asyncio
async def test_message_id_inserted_by_another_process_before_commit_does_not_lose_the_batch(
    db, world, evolution, monkeypatch
):
    """O webhook (outro processo) grava `m3` entre a checagem de duplicadas e o commit do lote."""
    real_existing = history_sync._existing_message_ids
    raced = []

    def racing_existing(session, ids):
        found = real_existing(session, ids)
        if not raced:
            raced.append(True)
            other = TestingSessionLocal()
            other.add(Message(
                instance_id=world["instance"].id, remote_jid=PHONE, message_id="m3", direction="incoming",
                content="gravada pelo webhook", timestamp=datetime.fromtimestamp(T0 + 30, tz=timezone.utc),
            ))
            other.commit()
            other.close()
        return found

    monkeypatch.setattr(history_sync, "_existing_message_ids", racing_existing)

    result = await history_sync.sync_instance(db, world["instance"])

    db.expire_all()
    assert result["messages"] == 4  # as outras 4; `m3` é do outro processo
    stored = db.query(Message).filter(Message.message_id == "m3").all()
    assert [m.content for m in stored] == ["gravada pelo webhook"]
    assert db.query(Message).count() == 5 and db.query(Conversation).count() == 3


@pytest.mark.asyncio
async def test_sync_yields_to_the_event_loop_between_batches(db, world, evolution, monkeypatch):
    monkeypatch.setattr(history_sync, "COMMIT_EVERY", 1)
    ticks = []

    async def ticker():
        while True:
            ticks.append(1)
            await asyncio.sleep(0)

    task = asyncio.create_task(ticker())
    await history_sync.sync_instance(db, world["instance"])
    task.cancel()

    assert len(ticks) >= 5  # um por lote (5 Messages, 1 por commit)


class _FakeConnection:
    def __init__(self, acquired):
        self.acquired, self.statements, self.closed = acquired, [], False

    def execute(self, statement, params):
        sql = str(statement)
        self.statements.append(sql)
        return SimpleNamespace(scalar=lambda: self.acquired)

    def commit(self):
        pass

    def close(self):
        self.closed = True


def _postgres_db(connection):
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=lambda: connection)
    return SimpleNamespace(get_bind=lambda: bind)


@pytest.mark.asyncio
async def test_postgres_advisory_lock_is_held_during_the_import_and_released_after(world, monkeypatch):
    connection = _FakeConnection(acquired=True)
    seen = []

    async def fake_import(db, instance):
        seen.append(list(connection.statements))
        return {"conversations": 0, "messages": 0}

    monkeypatch.setattr(history_sync, "_import_history", fake_import)

    await history_sync.sync_instance(_postgres_db(connection), world["instance"])

    assert len(seen[0]) == 1 and "pg_try_advisory_lock" in seen[0][0]  # lock tomado antes de importar
    assert "pg_advisory_unlock" in connection.statements[-1] and connection.closed


@pytest.mark.asyncio
async def test_sync_raises_when_another_process_holds_the_lock(world, monkeypatch):
    connection = _FakeConnection(acquired=False)

    async def fake_import(db, instance):
        raise AssertionError("não pode importar sem o lock")

    monkeypatch.setattr(history_sync, "_import_history", fake_import)

    with pytest.raises(history_sync.SyncAlreadyRunning):
        await history_sync.sync_instance(_postgres_db(connection), world["instance"])

    assert all("pg_advisory_unlock" not in sql for sql in connection.statements) and connection.closed


@pytest.mark.asyncio
async def test_sync_batches_do_not_block_the_event_loop(db, world, evolution, monkeypatch):
    """A escrita do lote é bloqueante (banco): cada uma demora 0,25 s aqui e tem de rodar fora do loop (#93)."""
    import time

    from tests.loop_helpers import run_watched

    real_write = history_sync._write_batch

    def slow_write(*args, **kwargs):
        time.sleep(0.25)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(history_sync, "_write_batch", slow_write)

    def wipe():  # cada tentativa importa do zero
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.query(Contact).delete()
        db.commit()

    result, slow = await run_watched(lambda: history_sync.sync_instance(db, world["instance"]), reset=wipe)

    assert result == {"conversations": 3, "messages": 5}
    assert slow == []
