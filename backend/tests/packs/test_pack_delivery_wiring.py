"""Executor real + `CatalogOrdersPack`: a Recap só vale depois de `reply_delivered`, e a confirmação seguinte fecha o Order."""

from datetime import timedelta

import pytest
from pack_helpers import DELIVERED_AT, add_item, fill_delivery, make_world, order_of, tool_named
from agent_fakes import FakeMessagesClient, reply, text, tool_use

from app.agent import clock, executor
from app.packs import registry
from app.packs.catalog_orders import checkout
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def setup(db, monkeypatch):
    """Um Order pronto para a Recap (Company aberta) e um Gateway roteirizado ligado ao executor."""
    world = make_world(db)
    now = {"t": DELIVERED_AT - timedelta(minutes=2)}
    for module in (clock, executor, checkout):
        monkeypatch.setattr(module, "utc_now", lambda: now["t"])
    client = FakeMessagesClient([])
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (client, "fake-model", "low"))
    packs = [registry.CorePack(), CatalogOrdersPack()]
    return world, client, packs


async def _prepare(world):
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add_item(world, pedido)
    await fill_delivery(world, pedido)


async def _turn(world, packs, message, received_at):
    return await executor.handle_incoming(
        world.db, world.conversation, world.contact, world.instance, message, received_at, agent=None, packs=packs
    )


def _recap_script(client):
    client.script += [
        reply(tool_use("gerenciar_pedido", {"acao": "recapitular"}, "r1")),
        reply(text("Pizza Toscana, entrega no Centro, total R$ 50,00. Confirma?")),
    ]


def _finalize_script(client):
    client.script += [
        reply(tool_use("gerenciar_pedido", {"acao": "finalizar"}, "f1")),
        reply(text("Pedido confirmado!")),
    ]


async def test_confirmation_after_a_delivered_recap_closes_the_order(setup):
    world, client, packs = setup
    await _prepare(world)
    _recap_script(client)

    first = await _turn(world, packs, "quero fechar", DELIVERED_AT - timedelta(minutes=1))
    assert first.reply_text and first.turn_id
    assert order_of(world).recap_delivered_at is None  # ainda não chegou ao Contact

    executor.reply_delivered(world.db, world.conversation, packs, first.turn_id, DELIVERED_AT)
    assert order_of(world).recap_delivered_at is not None

    _finalize_script(client)
    await _turn(world, packs, "pode fechar", DELIVERED_AT + timedelta(minutes=1))

    assert order_of(world).status == "closed"


async def test_confirmation_without_delivering_the_recap_does_not_close_the_order(setup):
    world, client, packs = setup
    await _prepare(world)
    _recap_script(client)
    first = await _turn(world, packs, "quero fechar", DELIVERED_AT - timedelta(minutes=1))
    assert first.turn_id  # a resposta existe, mas o envio não aconteceu: ninguém chamou reply_delivered

    _finalize_script(client)
    await _turn(world, packs, "pode fechar", DELIVERED_AT + timedelta(minutes=1))

    assert order_of(world).status != "closed"
