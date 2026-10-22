"""Order e Session (ADR 0007): abandono ao abrir a Session nova, aviso ao Agent e retomada pedida pelo Contact."""

from decimal import Decimal

import pytest
from pack_helpers import add_item, call, make_world, new_turn, payload, tool_named

from app.models import CustomerOrder
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pack():
    return CatalogOrdersPack()


@pytest.fixture
def pedido(pack):
    return tool_named(pack.tools(), "gerenciar_pedido")


def _orders(world):
    world.db.expire_all()
    return world.db.query(CustomerOrder).filter_by(conversation_id=world.conversation.id).all()


def _status(world, number):
    return next(o.status for o in _orders(world) if o.order_number == number)


async def _abandon(world, pack):
    pack.on_session_start(world.db, world.conversation)
    world.db.commit()


async def test_new_session_abandons_the_open_order_and_keeps_its_items(world, pack, pedido):
    number = payload(await add_item(world, pedido, quantidade=2))["pedido"]["numero"]

    await _abandon(world, pack)

    order = _orders(world)[0]
    assert (order.order_number, order.status) == (number, "abandoned")
    assert [(i.item_name, i.quantity) for i in order.items] == [("Pizza Toscana", 2)]


@pytest.mark.parametrize("status", ["open", "collecting_data", "ready_for_confirmation"])
async def test_every_active_status_is_abandoned(world, pack, pedido, status):
    await add_item(world, pedido)
    _orders(world)[0].status = status
    world.db.commit()

    await _abandon(world, pack)

    assert _orders(world)[0].status == "abandoned"


@pytest.mark.parametrize("status", ["closed", "in_production", "sent", "delivered", "cancelled"])
async def test_orders_already_finished_are_never_touched(world, pack, pedido, status):
    await add_item(world, pedido)
    _orders(world)[0].status = status
    world.db.commit()

    await _abandon(world, pack)

    assert _orders(world)[0].status == status


async def test_other_conversations_keep_their_open_orders(world, pack, pedido):
    from app.models import Conversation

    other = Conversation(instance_id=world.instance.id, contact_id=world.contact.id, remote_jid=world.contact.remote_jid)
    world.db.add(other)
    world.db.commit()
    await add_item(world, pedido)

    pack.on_session_start(world.db, other)
    world.db.commit()

    assert _orders(world)[0].status == "open"


async def test_an_abandoned_order_is_never_resumed_by_adding_an_item(world, pack, pedido):
    old = payload(await add_item(world, pedido))["pedido"]["numero"]
    await _abandon(world, pack)

    new = payload(await add_item(world, pedido, name="Pizza Calabresa"))["pedido"]

    assert new["numero"] != old
    assert [i["nome"] for i in new["itens"]] == ["Pizza Calabresa"]
    assert _status(world, old) == "abandoned"


async def test_prompt_tells_the_agent_about_the_abandoned_order(world, pack, pedido):
    number = payload(await add_item(world, pedido, quantidade=2, observacao="sem cebola"))["pedido"]["numero"]
    await _abandon(world, pack)

    section = pack.system_prompt_section(world.ctx)

    assert number in section
    assert "2x Pizza Toscana (sem cebola)" in section
    assert "R$ 90,00" in section
    assert "retomar_pedido" in section


async def test_prompt_has_no_abandoned_note_without_an_abandoned_order(world, pack, pedido):
    await add_item(world, pedido)

    assert "## Pedido abandonado" not in pack.system_prompt_section(world.ctx)


async def test_prompt_drops_the_note_once_a_newer_order_exists(world, pack, pedido):
    await add_item(world, pedido)
    await _abandon(world, pack)
    assert "## Pedido abandonado" in pack.system_prompt_section(world.ctx)

    await add_item(world, pedido, name="Pizza Calabresa")
    assert "## Pedido abandonado" not in pack.system_prompt_section(world.ctx)

    # Mesmo depois de fechar o novo, o abandonado não volta a ser oferecido.
    new = next(o for o in _orders(world) if o.status == "open")
    new.status = "closed"
    world.db.commit()
    assert "## Pedido abandonado" not in pack.system_prompt_section(world.ctx)


async def test_empty_abandoned_order_is_not_offered(world, pack, pedido):
    await add_item(world, pedido)
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Pizza Toscana"].id)
    await _abandon(world, pack)

    assert "## Pedido abandonado" not in pack.system_prompt_section(world.ctx)


async def test_resume_recreates_the_order_from_the_abandoned_one(world, pack, pedido):
    old = payload(await add_item(world, pedido, quantidade=2, observacao="sem cebola"))["pedido"]["numero"]
    await call(pedido, world.ctx, acao="adicionar_item", item_id=world.items["Suco de Laranja"].id)
    await _abandon(world, pack)

    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert not result.is_error
    data = payload(result)["pedido"]
    assert data["numero"] != old and data["status"] == "open"
    assert [(i["nome"], i["quantidade"], i["observacao"]) for i in data["itens"]] == [
        ("Pizza Toscana", 2, "sem cebola"),
        ("Suco de Laranja", 1, None),
    ]
    assert data["total"] == 99.5
    assert _status(world, old) == "abandoned"
    assert "## Pedido abandonado" not in pack.system_prompt_section(world.ctx)


async def test_resume_uses_current_catalog_prices_and_reports_unavailable_items(world, pack, pedido):
    await add_item(world, pedido)
    await add_item(world, pedido, name="Pizza Calabresa")
    await _abandon(world, pack)
    world.items["Pizza Toscana"].price = Decimal("50.00")
    world.items["Pizza Calabresa"].is_available = False
    world.db.commit()

    data = payload(await call(pedido, world.ctx, acao="retomar_pedido"))

    assert [(i["nome"], i["preco_unitario"]) for i in data["pedido"]["itens"]] == [("Pizza Toscana", 50.0)]
    assert data["indisponiveis"] == ["Pizza Calabresa"]


async def test_resume_with_nothing_available_fails_and_creates_no_order(world, pack, pedido):
    await add_item(world, pedido)
    await _abandon(world, pack)
    world.items["Pizza Toscana"].is_available = False
    world.db.commit()

    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert result.is_error
    assert [o.status for o in _orders(world)] == ["abandoned"]


async def test_resume_without_an_abandoned_order_fails(world, pedido):
    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert result.is_error and "abandonado" in payload(result)["erro"]


async def test_resume_is_refused_while_another_order_is_being_built(world, pack, pedido):
    await add_item(world, pedido)
    await _abandon(world, pack)
    await add_item(world, pedido, name="Pizza Calabresa")

    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert result.is_error
    assert len([o for o in _orders(world) if o.status == "open"]) == 1


async def test_same_as_yesterday_from_a_closed_order_via_status_then_add_item(world, pack, pedido):
    status = tool_named(pack.tools(), "status_pedido")
    await add_item(world, pedido, quantidade=2, observacao="sem cebola")
    await add_item(world, pedido, name="Suco de Laranja")
    old = _orders(world)[0]
    old.status = "closed"  # fechado e entregue na Session anterior
    world.db.commit()
    pack.on_session_start(world.db, world.conversation)
    world.db.commit()
    assert _orders(world)[0].status == "closed"  # só o Order ativo é abandonado

    world.items["Pizza Toscana"].price = Decimal("50.00")  # o cardápio mudou desde ontem
    world.db.commit()
    previous = payload(await call(status, world.ctx))["pedido"]
    new_turn(world)  # o Contact pede "o mesmo de ontem" num Turn novo
    for line in previous["itens"]:
        added = await call(
            pedido,
            world.ctx,
            acao="adicionar_item",
            item_id=line["item_id"],
            quantidade=line["quantidade"],
            **({"observacao": line["observacao"]} if line["observacao"] else {}),
        )
        assert not added.is_error

    current = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]
    assert current["numero"] != previous["numero"] and current["status"] == "open"
    assert [(i["nome"], i["quantidade"], i["observacao"], i["preco_unitario"]) for i in current["itens"]] == [
        ("Pizza Toscana", 2, "sem cebola", 50.0),
        ("Suco de Laranja", 1, None, 9.5),
    ]
    assert current["total"] == 109.5
    assert _status(world, previous["numero"]) == "closed"
