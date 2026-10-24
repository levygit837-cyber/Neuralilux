"""#92: sem Postgres o lock por Conversation vale só dentro do processo (asyncio.Lock por chave)."""
import asyncio

import pytest
from sqlalchemy import create_engine

from app.core import conversation_lock as cl
from app.core.conversation_lock import SUMMARY, TURN, LockBusy, conversation_lock

pytestmark = pytest.mark.asyncio


@pytest.fixture
def bind():
    engine = create_engine("sqlite://")
    yield engine
    engine.dispose()


async def test_same_key_never_overlaps_and_keeps_arrival_order(bind):
    inside, overlaps, order = 0, [], []

    async def worker(n):
        nonlocal inside
        async with conversation_lock(bind, TURN, "conv-1", wait=5):
            inside += 1
            overlaps.append(inside)
            order.append(n)
            await asyncio.sleep(0.01)
            inside -= 1

    await asyncio.gather(*(worker(n) for n in range(4)))

    assert max(overlaps) == 1
    assert order == [0, 1, 2, 3]
    assert cl._local == {}


async def test_zero_wait_gives_up_when_busy_and_works_again_after_release(bind):
    async with conversation_lock(bind, TURN, "conv-1"):
        with pytest.raises(LockBusy):
            async with conversation_lock(bind, TURN, "conv-1"):
                pytest.fail("não podia entrar")

    async with conversation_lock(bind, TURN, "conv-1"):
        pass
    assert cl._local == {}


async def test_wait_expires_with_lock_busy_and_leaves_nothing_behind(bind):
    async with conversation_lock(bind, TURN, "conv-1"):
        with pytest.raises(LockBusy):
            async with conversation_lock(bind, TURN, "conv-1", wait=0.05):
                pytest.fail("não podia entrar")
        assert len(cl._local) == 1  # só o lock de quem segura

    assert cl._local == {}


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
