"""Frase de Handoff: empatia do Agent mais a janela de atendimento humano da Company."""
from datetime import datetime, timezone

import pytest
from pack_helpers import call, make_world, tool_named

from app.agent import core_tools
from app.agent.core_tools import TRANSFER_MESSAGE, core_tools as build_core_tools
from app.models import Ticket

pytestmark = pytest.mark.asyncio

EMPATHY = "Sinto muito pelo transtorno com o seu pedido."


@pytest.fixture
def world(db, monkeypatch):
    async def publish(event):
        return None

    monkeypatch.setattr(core_tools, "publish_event", publish)
    return make_world(db)


def at(monkeypatch, *args):
    # make_world usa America/Fortaleza (UTC-3) com 18:00-23:00 de segunda a quinta.
    monkeypatch.setattr(core_tools, "utc_now", lambda: datetime(*args, tzinfo=timezone.utc))


async def transfer(world, **extra):
    tool = tool_named(build_core_tools(), "transferir_atendente")
    return await call(tool, world.ctx, motivo="Pedido veio errado", **extra)


async def test_open_hours_reply_is_the_empathy_then_the_fixed_phrase(world, monkeypatch):
    at(monkeypatch, 2026, 10, 19, 22, 0)  # segunda 19:00 local

    result = await transfer(world, frase_empatica=EMPATHY)

    assert result.ends_turn is True and not result.is_error
    assert result.content == f"{EMPATHY} {TRANSFER_MESSAGE}"


async def test_after_hours_reply_says_when_the_next_window_opens_today(world, monkeypatch):
    at(monkeypatch, 2026, 10, 19, 15, 0)  # segunda 12:00 local, abre às 18:00

    result = await transfer(world, frase_empatica=EMPATHY)

    assert result.content.startswith(EMPATHY)
    assert "fora do horário" in result.content and "hoje às 18:00" in result.content
    assert TRANSFER_MESSAGE not in result.content


async def test_after_hours_reply_points_to_tomorrow(world, monkeypatch):
    at(monkeypatch, 2026, 10, 20, 2, 30)  # segunda 23:30 local, já fechou; terça abre às 18:00

    result = await transfer(world, frase_empatica=EMPATHY)

    assert "amanhã às 18:00" in result.content


async def test_friday_midnight_close_points_to_saturday_window(world, monkeypatch):
    at(monkeypatch, 2026, 10, 24, 3, 30)  # sábado 00:30 local: sexta fechou 00:00, sábado abre 18:00

    result = await transfer(world, frase_empatica=EMPATHY)

    assert "hoje às 18:00" in result.content


async def test_company_without_hours_always_uses_the_fixed_phrase(world, monkeypatch):
    world.company.business_hours = None
    world.db.commit()
    at(monkeypatch, 2026, 10, 19, 15, 0)

    result = await transfer(world, frase_empatica=EMPATHY)

    assert result.content == f"{EMPATHY} {TRANSFER_MESSAGE}"


async def test_blank_empathy_falls_back_to_the_fixed_phrase_alone(world, monkeypatch):
    at(monkeypatch, 2026, 10, 19, 22, 0)

    result = await transfer(world, frase_empatica="  \n ")

    assert result.content == TRANSFER_MESSAGE


async def test_multiline_empathy_is_collapsed_to_one_line(world, monkeypatch):
    at(monkeypatch, 2026, 10, 19, 22, 0)

    result = await transfer(world, frase_empatica="Entendo\n\nvocê.")

    assert result.content.startswith("Entendo você. ")


async def test_repeated_transfer_still_ends_the_turn_without_a_second_ticket(world, monkeypatch):
    at(monkeypatch, 2026, 10, 19, 22, 0)
    await transfer(world, frase_empatica=EMPATHY)

    second = await transfer(world, frase_empatica=EMPATHY)

    assert second.ends_turn is True
    assert world.db.query(Ticket).count() == 1
