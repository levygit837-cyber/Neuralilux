"""TurnBatcher: agrupa as Messages picadas de uma Conversation num Turn, sem perder nem sobrepor, com relógio falso."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.whatsapp.turn_batcher import Entry, TurnBatcher
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
        self.groups = []
        self.gate: asyncio.Event | None = None
        self.running = 0
        self.max_running = 0

    @property
    def texts(self) -> list[str]:
        return [group.text for group in self.groups]

    @property
    def ids(self) -> list[tuple[str, ...]]:
        return [group.message_ids for group in self.groups]

    @property
    def received(self) -> list[datetime]:
        return [group.received_at for group in self.groups]

    async def __call__(self, group) -> None:
        self.groups.append(group)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            if self.gate is not None:
                await self.gate.wait()
        finally:
            self.running -= 1


def entry(text: str, at: datetime = T0, message_id: str | None = None) -> Entry:
    return Entry(message_id or f"id-{text}", text, at)


def submit(batcher, key, text, run, window=WINDOW, at=T0, hold=None):
    return asyncio.create_task(batcher.submit(key, entry(text, at), run, window, hold))


@pytest.mark.asyncio
async def test_messages_inside_the_window_become_one_turn_with_all_of_them(batcher, clock):
    runs = Runs()
    tasks = [submit(batcher, "c1", "oi", runs)]
    await settle()
    await clock.advance(1)
    tasks.append(submit(batcher, "c1", "quero", runs))
    await settle()
    await clock.advance(1)
    tasks.append(submit(batcher, "c1", "uma calabresa", runs))
    await settle()
    assert runs.texts == []

    await clock.advance(WINDOW)
    await asyncio.gather(*tasks)

    assert runs.texts == ["oi\nquero\numa calabresa"]
    assert runs.ids == [("id-oi", "id-quero", "id-uma calabresa")]


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
    await clock.advance(WINDOW)
    assert runs.texts == ["oi"]

    late = submit(batcher, "c1", "sem cebola", runs)
    await settle()
    assert late.done() and runs.texts == ["oi"]  # entrou na fila, não abriu outro Turn

    runs.gate.set()
    await settle()
    await clock.advance(WINDOW)
    await leader

    assert runs.texts == ["oi", "sem cebola"]
    assert runs.max_running == 1


@pytest.mark.asyncio
async def test_different_conversations_run_in_parallel(batcher, clock):
    runs = Runs()
    runs.gate = asyncio.Event()
    a = submit(batcher, "a", "a1", runs)
    b = submit(batcher, "b", "b1", runs)
    await settle()
    await clock.advance(WINDOW)

    assert sorted(runs.texts) == ["a1", "b1"]
    assert runs.max_running == 2

    runs.gate.set()
    await asyncio.gather(a, b)


@pytest.mark.asyncio
async def test_failing_turn_does_not_lose_the_messages_that_arrived_meanwhile(batcher, clock):
    texts = []
    gate = asyncio.Event()

    async def run(group):
        texts.append(group.text)
        if len(texts) == 1:
            await gate.wait()
            raise RuntimeError("modelo caiu")

    leader = submit(batcher, "c1", "primeira", run)
    await settle()
    await clock.advance(WINDOW)
    submit(batcher, "c1", "segunda", run)
    await settle()
    gate.set()
    await settle()
    await clock.advance(WINDOW)
    await leader  # o erro do Turn não sobe

    assert texts == ["primeira", "segunda"]


@pytest.mark.asyncio
async def test_state_is_released_when_idle(batcher, clock):
    runs = Runs()
    task = submit(batcher, "c1", "oi", runs)
    await settle()
    await clock.advance(WINDOW)
    await task

    assert batcher.active == set()
    assert batcher._holds == {}


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


@pytest.mark.asyncio
async def test_message_stored_but_not_yet_submitted_joins_the_group_and_is_never_in_two_turns(batcher, clock):
    """Seguidora gravada na hora em que a janela fecha: a líder espera o `submit` dela e a leva no mesmo grupo."""
    runs = Runs()
    leader = submit(batcher, "c1", "oi", runs)
    await settle()
    hold = batcher.hold("c1")  # a seguidora commitou; ainda não chegou ao submit
    await clock.advance(WINDOW)  # a janela fecha com a seguidora a caminho
    assert runs.texts == []  # a líder não fechou o grupo

    follower = submit(batcher, "c1", "quero", runs, hold=hold)
    await settle()
    await clock.advance(WINDOW)
    await asyncio.gather(leader, follower)

    assert runs.ids == [("id-oi", "id-quero")]  # exatamente uma vez, no mesmo Turn


@pytest.mark.asyncio
async def test_released_hold_without_submit_does_not_block_the_leader(batcher, clock):
    """Seguidora que não vai ao Agent (ex.: Handoff) solta a marca; a líder segue."""
    runs = Runs()
    leader = submit(batcher, "c1", "oi", runs)
    await settle()
    hold = batcher.hold("c1")
    await clock.advance(WINDOW)
    hold.release()
    hold.release()  # idempotente
    await settle()
    await clock.advance(WINDOW)
    await leader

    assert runs.texts == ["oi"]
    assert batcher._holds == {}


@pytest.mark.asyncio
async def test_zero_window_runs_one_turn_per_message_in_arrival_order(batcher):
    runs = Runs()
    runs.gate = asyncio.Event()
    first = submit(batcher, "c1", "oi", runs, window=0)
    await settle()
    second = submit(batcher, "c1", "quero", runs, window=0)
    third = submit(batcher, "c1", "uma calabresa", runs, window=0)
    await settle()
    assert runs.texts == ["oi"]  # as outras esperam na fila; nenhum Turn sobreposto

    runs.gate.set()
    await asyncio.gather(first, second, third)

    assert runs.texts == ["oi", "quero", "uma calabresa"]
    assert runs.max_running == 1
