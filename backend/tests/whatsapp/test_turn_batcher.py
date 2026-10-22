"""TurnBatcher: agrupa as Messages picadas de uma Conversation num Turn, sem perder nem sobrepor, com relógio falso."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.whatsapp.turn_batcher import TurnBatcher
from tests.clock_helpers import FakeClock, settle

WINDOW = 3.0
T0 = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def batcher(clock):
    return TurnBatcher(monotonic=clock.monotonic, sleep=clock.sleep)


class Runs:
    """Registra cada Turn; `gate`, se definido, segura o Turn até o teste soltar."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.received: list[datetime] = []
        self.running = 0
        self.max_running = 0
        self.gate: asyncio.Event | None = None

    async def __call__(self, text: str, received_at: datetime) -> None:
        self.texts.append(text)
        self.received.append(received_at)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            if self.gate is not None:
                await self.gate.wait()
        finally:
            self.running -= 1


def submit(batcher, key, text, run, window=WINDOW, at=T0):
    return asyncio.create_task(batcher.submit(key, text, at, run, window))


@pytest.mark.asyncio
async def test_messages_inside_the_window_become_one_turn_with_all_of_them(batcher, clock):
    runs = Runs()
    tasks = [submit(batcher, "c1", "oi", runs)]
    await settle()
    await clock.advance(1)
    tasks.append(submit(batcher, "c1", "quero", runs))
    await clock.advance(1)
    tasks.append(submit(batcher, "c1", "uma calabresa", runs))
    await settle()

    await clock.advance(2.9)  # a janela conta da última Message: ainda não passou
    assert runs.texts == []

    await clock.advance(0.2)
    await asyncio.gather(*tasks)
    assert runs.texts == ["oi\nquero\numa calabresa"]


@pytest.mark.asyncio
async def test_a_message_after_the_pause_starts_a_new_turn(batcher, clock):
    runs = Runs()
    first = submit(batcher, "c1", "oi", runs)
    await settle()
    await clock.advance(WINDOW)
    await first

    second = submit(batcher, "c1", "e o cardápio?", runs)
    await settle()
    await clock.advance(WINDOW)
    await second

    assert runs.texts == ["oi", "e o cardápio?"]


@pytest.mark.asyncio
async def test_followers_return_at_once_and_only_the_first_submit_waits_for_the_turn(batcher, clock):
    runs = Runs()
    leader = submit(batcher, "c1", "oi", runs)
    await settle()
    follower = submit(batcher, "c1", "quero", runs)
    await settle()

    assert follower.done() and not leader.done()

    await clock.advance(WINDOW)
    await leader
    assert runs.texts == ["oi\nquero"]


@pytest.mark.asyncio
async def test_message_during_a_turn_waits_for_the_next_turn_without_overlap_or_loss(batcher, clock):
    runs = Runs()
    runs.gate = asyncio.Event()
    leader = submit(batcher, "c1", "oi", runs)
    await settle()
    await clock.advance(WINDOW)  # o Turn começa e fica preso no gate
    assert runs.texts == ["oi"]

    late = submit(batcher, "c1", "esqueci: sem cebola", runs)
    await settle()
    assert late.done() and runs.texts == ["oi"]  # não dispara um segundo Turn por cima

    runs.gate.set()
    await settle()
    assert runs.texts == ["oi"]  # o Turn seguinte ainda espera a pausa da Message nova
    await clock.advance(WINDOW)
    await leader

    assert runs.texts == ["oi", "esqueci: sem cebola"]
    assert runs.max_running == 1


@pytest.mark.asyncio
async def test_different_conversations_run_in_parallel(batcher, clock):
    runs = Runs()
    runs.gate = asyncio.Event()
    a = submit(batcher, "c1", "a", runs)
    b = submit(batcher, "c2", "b", runs)
    await settle()
    await clock.advance(WINDOW)

    assert sorted(runs.texts) == ["a", "b"] and runs.max_running == 2

    runs.gate.set()
    await asyncio.gather(a, b)


@pytest.mark.asyncio
async def test_failing_turn_does_not_lose_the_messages_that_arrived_meanwhile(batcher, clock):
    texts = []

    async def run(text, received_at):
        texts.append(text)
        if len(texts) == 1:
            submit(batcher, "c1", "segunda", run)  # chega durante o primeiro Turn
            await settle()
            raise RuntimeError("gateway fora")

    leader = submit(batcher, "c1", "primeira", run)
    await settle()
    await clock.advance(WINDOW)
    await settle()
    await clock.advance(WINDOW)
    await leader  # a falha não sobe: a entrega não é reprocessada

    assert texts == ["primeira", "segunda"]


@pytest.mark.asyncio
async def test_state_is_released_when_idle(batcher, clock):
    runs = Runs()
    task = submit(batcher, "c1", "oi", runs)
    await settle()
    await clock.advance(WINDOW)
    await task

    assert batcher.active == set()


@pytest.mark.asyncio
async def test_zero_window_runs_immediately(batcher):
    runs = Runs()

    await batcher.submit("c1", "oi", T0, runs, 0)

    assert runs.texts == ["oi"]


@pytest.mark.asyncio
async def test_grouped_turn_carries_the_timestamp_of_the_oldest_message(batcher, clock):
    runs = Runs()
    tasks = [submit(batcher, "c1", "oi", runs, at=T0 + timedelta(seconds=2))]
    await settle()
    tasks.append(submit(batcher, "c1", "quero", runs, at=T0))  # chegou fora de ordem, é a mais antiga
    tasks.append(submit(batcher, "c1", "uma calabresa", runs, at=T0 + timedelta(seconds=5)))
    await settle()
    await clock.advance(WINDOW)
    await asyncio.gather(*tasks)

    assert runs.received == [T0]


@pytest.mark.asyncio
async def test_next_turn_starts_its_own_oldest_timestamp(batcher, clock):
    runs = Runs()
    runs.gate = asyncio.Event()
    leader = submit(batcher, "c1", "oi", runs, at=T0)
    await settle()
    await clock.advance(WINDOW)
    submit(batcher, "c1", "sem cebola", runs, at=T0 + timedelta(seconds=10))
    await settle()
    runs.gate.set()
    await settle()
    await clock.advance(WINDOW)
    await leader

    assert runs.received == [T0, T0 + timedelta(seconds=10)]
