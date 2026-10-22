"""`typing_indicator`: a presença "digitando" é renovada enquanto o Turn roda e para quando ele termina."""
import asyncio

import pytest

from app.core.config import settings
from app.whatsapp.agent_turn import typing_indicator
from app.whatsapp.evolution_client import EvolutionAPIError, evolution_api
from tests.clock_helpers import FakeClock, settle

pytestmark = pytest.mark.asyncio


@pytest.fixture
def calls(monkeypatch):
    """Presença falsa que volta na hora, como uma Evolution que já mostrou o "digitando"."""
    sent: list[tuple[float, int]] = []
    state = {"clock": None}

    async def send_presence(instance_name, remote_jid, presence="composing", delay_ms=0):
        sent.append((state["clock"].now, delay_ms))

    monkeypatch.setattr(evolution_api, "send_presence", send_presence)
    monkeypatch.setattr(settings, "TYPING_REFRESH_SECONDS", 20.0)
    return sent, state


async def test_presence_is_sent_at_0_20_and_40_seconds_of_a_45_second_turn_then_stops(calls):
    sent, state = calls
    clock = state["clock"] = FakeClock()

    async with typing_indicator("evo", "5511999990001@s.whatsapp.net", clock.sleep, clock.monotonic):
        await settle()
        for _ in range(45):
            await clock.advance(1)

    assert [at for at, _ in sent] == [0.0, 20.0, 40.0]
    assert {delay for _, delay in sent} == {20000}  # o delay cobre o intervalo até a próxima renovação

    await clock.advance(60)
    assert len(sent) == 3  # terminou o Turn: nenhuma renovação depois


async def test_presence_failure_ends_the_loop_without_raising(calls, monkeypatch):
    sent, state = calls
    clock = state["clock"] = FakeClock()
    attempts = []

    async def broken(instance_name, remote_jid, presence="composing", delay_ms=0):
        attempts.append(clock.now)
        raise EvolutionAPIError("desconectada", status_code=500)

    monkeypatch.setattr(evolution_api, "send_presence", broken)

    async with typing_indicator("evo", "5511999990001@s.whatsapp.net", clock.sleep, clock.monotonic):
        await settle()
        await clock.advance(60)

    assert attempts == [0.0]  # uma tentativa, sem insistir
