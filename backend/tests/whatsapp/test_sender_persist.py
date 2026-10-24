"""`send_and_persist` (#93): a Message `from_me` está commitada antes de publicar e antes de soltar o lock `SAVE`,
inclusive quando o Turn é cancelado com a gravação em thread ainda rodando."""
import asyncio
import threading

import pytest

from app.core.config import settings
from app.core.conversation_lock import SAVE, LockBusy, conversation_lock, jid_scope
from app.models import Contact, Instance, Message
from app.whatsapp import sender
from tests.access_helpers import fake_text_sender
from tests.conftest import TestingSessionLocal

pytestmark = pytest.mark.asyncio


@pytest.fixture
def parts(db, conversation_factory, monkeypatch):
    conversation = conversation_factory("conv-sender")
    fake_text_sender(monkeypatch)
    return db.get(Instance, conversation.instance_id), conversation, db.get(Contact, conversation.contact_id)


def _saved_from_me() -> int:
    """Conta as Messages `from_me` commitadas, lidas por outra Session (como o eco do webhook em outra réplica)."""
    other = TestingSessionLocal()
    try:
        return other.query(Message).filter(Message.is_from_me.is_(True)).count()
    finally:
        other.close()


async def test_the_reply_is_committed_before_it_is_published(db, parts, monkeypatch):
    instance, conversation, contact = parts
    seen = []

    async def spy(*args, **kwargs):
        seen.append(_saved_from_me())

    monkeypatch.setattr(sender, "publish_message", spy)

    await sender.send_and_persist(db, instance, conversation, contact, "Olá")

    assert seen == [1]


async def test_cancelling_the_turn_keeps_the_save_lock_until_the_thread_has_committed(db, parts, monkeypatch):
    instance, conversation, contact = parts
    scope = jid_scope(instance.id, conversation.remote_jid)
    started, release = threading.Event(), threading.Event()
    real_persist = sender._persist_reply

    def slow_persist(*args):
        started.set()
        assert release.wait(10)
        real_persist(*args)

    monkeypatch.setattr(sender, "_persist_reply", slow_persist)

    async def no_publish(*args, **kwargs):
        pytest.fail("um Turn cancelado não publica")

    monkeypatch.setattr(sender, "publish_message", no_publish)
    task = asyncio.ensure_future(sender.send_and_persist(db, instance, conversation, contact, "Olá"))
    while not started.is_set():
        await asyncio.sleep(0.001)

    task.cancel()
    for _ in range(20):  # o cancelamento tem tempo de sobra para soltar o lock, se fosse soltá-lo
        await asyncio.sleep(0.005)
    assert not task.done()  # espera a thread
    with pytest.raises(LockBusy):  # o eco de outra réplica ainda não pode gravar
        async with conversation_lock(db.get_bind(), SAVE, scope, wait=0):
            pass

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert _saved_from_me() == 1  # commitada quando o lock foi solto
    async with conversation_lock(db.get_bind(), SAVE, scope, wait=settings.LOCK_SAVE_WAIT_SECONDS):
        pass
