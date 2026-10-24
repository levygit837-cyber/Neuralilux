"""#92: o lock por Conversation é um advisory lock do Postgres, valendo entre conexões (réplicas) de verdade."""
import asyncio

import pytest
from sqlalchemy import create_engine, text

from app.core import conversation_lock as cl
from app.core.config import settings
from app.core.conversation_lock import SUMMARY, TURN, LockBusy, conversation_lock

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


@pytest.fixture
def bind(make_database):
    engine = create_engine(make_database())
    yield engine
    cl.dispose_lock_engines()
    engine.dispose()


async def test_second_holder_is_refused_until_the_first_releases(bind):
    async with conversation_lock(bind, TURN, "conv-1"):
        with pytest.raises(LockBusy):
            async with conversation_lock(bind, TURN, "conv-1"):
                pytest.fail("não podia entrar")

    async with conversation_lock(bind, TURN, "conv-1"):
        pass


async def test_waiter_gets_the_lock_when_the_holder_leaves(bind):
    order = []

    async def holder():
        async with conversation_lock(bind, TURN, "conv-1"):
            order.append("holder in")
            await asyncio.sleep(0.5)
            order.append("holder out")

    async def waiter():
        await asyncio.sleep(0.1)
        async with conversation_lock(bind, TURN, "conv-1", wait=10):
            order.append("waiter in")

    await asyncio.gather(holder(), waiter())

    assert order == ["holder in", "holder out", "waiter in"]


async def test_other_conversation_and_other_kind_do_not_wait(bind):
    async with conversation_lock(bind, TURN, "conv-1"):
        async with conversation_lock(bind, TURN, "conv-2"), conversation_lock(bind, SUMMARY, "conv-1"):
            pass


async def test_lock_is_released_when_the_block_raises(bind):
    with pytest.raises(RuntimeError):
        async with conversation_lock(bind, TURN, "conv-1"):
            raise RuntimeError("boom")

    async with conversation_lock(bind, TURN, "conv-1"):
        pass


async def test_waiting_does_not_hold_a_lock_connection(bind, monkeypatch):
    """Pool de 2: o titular usa uma conexão. Quem espera o mesmo lock não pode ocupar a outra, ou o terceiro falha."""
    monkeypatch.setattr(settings, "LOCK_POOL_SIZE", 2)
    async with conversation_lock(bind, TURN, "conv-1"):
        waiter = asyncio.create_task(_wait_for(bind, "conv-1"))
        await asyncio.sleep(0.5)  # várias tentativas do waiter
        async with conversation_lock(bind, TURN, "conv-2"):
            pass
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def _wait_for(bind, ident):
    async with conversation_lock(bind, TURN, ident, wait=30):
        pass


async def test_exhausted_lock_pool_counts_as_busy_instead_of_blocking(bind, monkeypatch):
    monkeypatch.setattr(settings, "LOCK_POOL_SIZE", 1)
    async with conversation_lock(bind, TURN, "conv-1"):
        with pytest.raises(LockBusy):
            async with conversation_lock(bind, TURN, "conv-2"):
                pytest.fail("não podia entrar")

    async with conversation_lock(bind, TURN, "conv-2"):
        pass


async def test_lock_dies_with_the_holder_connection(bind):
    """Réplica morta: o Postgres fecha a conexão e o lock some sem ninguém soltá-lo."""
    async with conversation_lock(bind, TURN, "conv-1"):
        with bind.connect() as admin:
            admin.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_locks "
                    "WHERE locktype = 'advisory' AND granted AND pid <> pg_backend_pid()"
                )
            )
            admin.commit()

        async with conversation_lock(bind, TURN, "conv-1", wait=5):
            pass
