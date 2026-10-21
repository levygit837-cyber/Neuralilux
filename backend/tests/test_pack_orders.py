from decimal import Decimal

import pytest
from pack_helpers import call, make_world, payload, tool_named

from app.models.models import CustomerOrder, PaymentRecord
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio

ENDERECO = "Rua das Flores 123, Centro"


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")


def order_of(world) -> CustomerOrder:
    world.db.expire_all()
    return world.db.query(CustomerOrder).filter_by(conversation_id=world.conversation.id).one()


async def add(world, pedido, name="Pizza Toscana", **kw):
    return await call(pedido, world.ctx, acao="adicionar_item", item_id=world.items[name].id, **kw)


async def fill_delivery(world, pedido, **overrides):
    data = dict(nome="Maria Silva", endereco=ENDERECO, tipo_entrega="entrega", forma_pagamento="dinheiro")
    data.update(overrides)
    return await call(pedido, world.ctx, acao="definir_dados", **data)


# ---------- itens ----------


async def test_add_item_uses_catalog_price_and_quantity(world, pedido):
    result = await add(world, pedido, quantidade=2, observacao="sem cebola")
    assert not result.is_error
    data = payload(result)["pedido"]
    assert data["subtotal"] == 90.0
    assert data["itens"][0]["quantidade"] == 2
    assert data["itens"][0]["observacao"] == "sem cebola"
    order = order_of(world)
    assert order.contact_id == world.contact.id and order.instance_id == world.instance.id
    assert order.total_amount == Decimal("90.00")


async def test_same_item_and_note_accumulates_quantity(world, pedido):
    await add(world, pedido, quantidade=1)
    await add(world, pedido, quantidade=2)
    items = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"]
    assert len(items) == 1 and items[0]["quantidade"] == 3


async def test_unavailable_item_is_refused(world, pedido):
    result = await add(world, pedido, name="Pizza Portuguesa")
    assert result.is_error
    assert "indispon" in payload(result)["erro"].lower()
    assert world.db.query(CustomerOrder).count() == 0


async def test_item_from_other_company_is_refused(world, pedido):
    result = await call(pedido, world.ctx, acao="adicionar_item", item_id=world.other_company_item.id)
    assert result.is_error
    assert world.db.query(CustomerOrder).count() == 0


async def test_unknown_item_and_bad_quantity_are_refused(world, pedido):
    assert (await call(pedido, world.ctx, acao="adicionar_item", item_id="nope")).is_error
    assert (await call(pedido, world.ctx, acao="adicionar_item")).is_error
    assert (await add(world, pedido, quantidade=0)).is_error
    assert (await add(world, pedido, quantidade=-1)).is_error


async def test_remove_item_partial_and_total(world, pedido):
    await add(world, pedido, quantidade=3)
    await add(world, pedido, name="Suco de Laranja")
    item_id = world.items["Pizza Toscana"].id

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id, quantidade=1))["pedido"]
    assert [i["quantidade"] for i in data["itens"]] == [2, 1]
    assert data["subtotal"] == 99.5

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id))["pedido"]
    assert [i["nome"] for i in data["itens"]] == ["Suco de Laranja"]
    assert data["subtotal"] == 9.5


async def test_remove_item_not_in_order_is_error(world, pedido):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Suco de Laranja"].id)
    assert result.is_error


async def test_ver_without_order_says_empty(world, pedido):
    result = await call(pedido, world.ctx, acao="ver")
    assert not result.is_error
    assert payload(result)["pedido"] is None


async def test_unknown_action_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="iniciar_finalizacao")).is_error


async def test_action_enum_matches_handler(pedido):
    enum = pedido.input_schema["properties"]["acao"]["enum"]
    assert enum == ["adicionar_item", "remover_item", "ver", "definir_dados", "finalizar"]


# ---------- validação de dados ----------


@pytest.mark.parametrize("nome", ["retirada", "Pix", "  ENTREGA ", "a", "12", "ok", "dinheiro"])
async def test_invalid_names_are_refused(world, pedido, nome):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome=nome)
    assert result.is_error
    assert order_of(world).customer_name is None


async def test_valid_name_is_stored(world, pedido):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome="Zé")
    assert not result.is_error
    assert order_of(world).customer_name == "Zé"


@pytest.mark.parametrize("endereco", ["Rua A 1", "Rua das Flores sem numero", "12345678", "centro"])
async def test_invalid_delivery_addresses_are_refused(world, pedido, endereco):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="entrega", endereco=endereco)
    assert result.is_error


async def test_address_not_required_for_pickup(world, pedido):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="retirada", nome="Maria")
    assert not result.is_error
    assert payload(result)["pedido"]["faltando"] == ["forma_pagamento"]


async def test_invalid_enums_are_refused(world, pedido):
    await add(world, pedido)
    assert (await call(pedido, world.ctx, acao="definir_dados", forma_pagamento="boleto")).is_error
    assert (await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="drone")).is_error


async def test_invalid_field_saves_nothing(world, pedido):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome="Maria", forma_pagamento="boleto")
    assert result.is_error
    assert order_of(world).customer_name is None


async def test_definir_dados_without_order_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="definir_dados", nome="Maria")).is_error


# ---------- total, taxa e mínimo ----------


async def test_total_includes_zone_fee_for_delivery(world, pedido):
    await add(world, pedido)
    await fill_delivery(world, pedido)
    data = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]
    assert data["subtotal"] == 45.0
    assert data["taxa_entrega"] == 5.0
    assert data["total"] == 50.0
    assert order_of(world).total_amount == Decimal("50.00")


async def test_pickup_has_no_fee(world, pedido):
    await add(world, pedido)
    await fill_delivery(world, pedido, tipo_entrega="retirada", endereco=None)
    data = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]
    assert data["taxa_entrega"] == 0 and data["total"] == 45.0


async def test_zone_of_other_company_or_legacy_is_not_used(world, pedido):
    await add(world, pedido)
    for bairro in ("Praia", "Meireles"):
        result = await fill_delivery(world, pedido, endereco=f"Rua do Mar 500, {bairro}")
        assert result.is_error
        assert "bairro" in payload(result)["erro"].lower()


async def test_delivery_without_configured_zone_is_unavailable(db):
    world = make_world(db, with_zone=False)
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add(world, pedido)
    result = await fill_delivery(world, pedido)
    assert result.is_error
    assert "retirada" in payload(result)["erro"].lower()


async def test_minimum_order_blocks_finalize_and_counts_items_only(world, pedido):
    await add(world, pedido, name="Suco de Laranja")  # 9.50 < mínimo 30
    await fill_delivery(world, pedido)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "30" in payload(result)["erro"]
    assert order_of(world).status != "closed"


async def test_minimum_is_checked_on_items_not_on_fee(world, pedido):
    # 25.00 de itens + 5.00 de taxa = 30.00, mas o mínimo vale para os itens.
    await add(world, pedido, name="Suco de Laranja", quantidade=2)  # 19.00
    await add(world, pedido, name="Refrigerante Cola 2L")  # 12.00 -> 31.00 ok
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Suco de Laranja"].id, quantidade=2)
    await add(world, pedido, name="Suco de Laranja")  # 21.50 de itens
    await fill_delivery(world, pedido)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


# ---------- finalizar ----------


async def test_finalize_requires_complete_data(world, pedido):
    await add(world, pedido)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    err = payload(result)["erro"]
    assert "nome" in err and "tipo_entrega" in err and "forma_pagamento" in err


async def test_finalize_delivery_requires_address(world, pedido):
    await add(world, pedido)
    await call(pedido, world.ctx, acao="definir_dados", nome="Maria", tipo_entrega="entrega", forma_pagamento="cartao")
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error and "endereco" in payload(result)["erro"]


async def test_finalize_without_items_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_finalize_cash_closes_order_with_total(world, pedido):
    await add(world, pedido)
    await fill_delivery(world, pedido, troco_para=100)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert not result.is_error
    data = payload(result)
    assert data["pedido"]["status"] == "closed"
    assert data["pedido"]["total"] == 50.0
    assert data["pedido"]["troco_para"] == 100.0
    assert "pix" not in data
    order = order_of(world)
    assert order.status == "closed" and order.closed_at is not None
    assert order.customer_phone == world.contact.phone_number
    assert world.db.query(PaymentRecord).count() == 0


async def test_change_must_cover_total(world, pedido):
    await add(world, pedido)
    result = await fill_delivery(world, pedido, troco_para=20)
    assert result.is_error
    result = await fill_delivery(world, pedido, forma_pagamento="cartao", troco_para=100)
    assert result.is_error


async def test_after_finalize_a_new_order_starts_empty(world, pedido):
    await add(world, pedido)
    await fill_delivery(world, pedido)
    await call(pedido, world.ctx, acao="finalizar")
    assert payload(await call(pedido, world.ctx, acao="ver"))["pedido"] is None
    await add(world, pedido, name="Suco de Laranja")
    assert world.db.query(CustomerOrder).count() == 2


# ---------- Pix ----------


def tlv(emv: str) -> dict[str, str]:
    out, i = {}, 0
    while i < len(emv):
        tag, size = emv[i : i + 2], int(emv[i + 2 : i + 4])
        out[tag] = emv[i + 4 : i + 4 + size]
        i += 4 + size
    return out


def crc16(text: str) -> str:
    crc = 0xFFFF
    for byte in text.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


async def finalize_pix(world, pedido):
    await add(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    return await call(pedido, world.ctx, acao="finalizar")


async def test_pix_uses_real_amount_company_key_and_order_txid(world, pedido):
    result = await finalize_pix(world, pedido)
    assert not result.is_error
    data = payload(result)
    emv = data["pix"]["copia_e_cola"]
    fields = tlv(emv)
    order = order_of(world)

    assert fields["54"] == "95.00"  # 2 x 45.00 + taxa 5.00, nunca um valor fixo
    assert fields["58"] == "BR" and fields["53"] == "986"
    account = tlv(fields["26"])
    assert account["00"] == "br.gov.bcb.pix" and account["01"] == world.company.pix_key
    txid = tlv(fields["62"])["05"]
    assert txid == order.order_number.replace("-", "")
    assert data["pix"]["txid"] == txid
    assert fields["63"] == crc16(emv[:-4])
    assert "outra@pix.example" not in result.content


async def test_pix_payment_record_is_deduplicated(world, pedido):
    first = payload(await finalize_pix(world, pedido))
    order = order_of(world)
    # Reaproveita o registro mesmo se o handler for reexecutado para o mesmo pedido.
    from app.packs.catalog_orders import pix

    again = pix.ensure_payment_record(world.db, order, world.company)
    records = world.db.query(PaymentRecord).all()
    assert len(records) == 1
    assert again.id == records[0].id
    assert records[0].amount == Decimal("95.00")
    assert records[0].qr_code_data == first["pix"]["copia_e_cola"]
    assert records[0].order_id == order.id and records[0].status == "pending"


async def test_pix_without_company_key_does_not_close_order(world, pedido):
    await add(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    world.company.pix_key = None  # chave removida entre a coleta e o fechamento
    world.db.commit()
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "pix" in payload(result)["erro"].lower()
    assert order_of(world).status != "closed"
    assert world.db.query(PaymentRecord).count() == 0


async def test_pix_forma_pagamento_not_offered_without_key_is_refused_early(db):
    world = make_world(db, pix_key=None)
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add(world, pedido)
    assert (await fill_delivery(world, pedido, forma_pagamento="pix")).is_error


# ---------- status_pedido ----------


async def test_status_without_orders(world):
    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    result = await call(status, world.ctx)
    assert not result.is_error
    assert payload(result)["pedido"] is None


async def test_status_returns_latest_order_of_the_contact(world, pedido):
    from datetime import datetime, timedelta, timezone

    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    await add(world, pedido, name="Suco de Laranja")
    await fill_delivery(world, pedido, tipo_entrega="retirada", endereco=None)
    old = order_of(world)
    old.status = "delivered"
    old.opened_at = old.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    world.db.commit()

    await add(world, pedido, quantidade=2)
    await fill_delivery(world, pedido)
    await call(pedido, world.ctx, acao="finalizar")
    last = payload(await call(status, world.ctx))["pedido"]
    assert last["status"] == "closed"
    assert last["total"] == 95.0
    assert [i["nome"] for i in last["itens"]] == ["Pizza Toscana"]
    assert last["numero"] == order_of_latest(world).order_number


def order_of_latest(world):
    world.db.expire_all()
    return world.db.query(CustomerOrder).order_by(CustomerOrder.opened_at.desc()).first()


async def test_status_never_shows_orders_of_another_contact(world, pedido):
    from app.models.models import Contact, Conversation

    other = Contact(instance_id=world.instance.id, phone_number="5585911112222", remote_jid="5585911112222@s.whatsapp.net")
    world.db.add(other)
    world.db.flush()
    conv = Conversation(instance_id=world.instance.id, contact_id=other.id, remote_jid=other.remote_jid)
    world.db.add(conv)
    world.db.flush()
    world.db.add(
        CustomerOrder(
            order_number="X-1",
            conversation_id=conv.id,
            instance_id=world.instance.id,
            contact_id=other.id,
            remote_jid=other.remote_jid,
            total_amount=Decimal("10"),
        )
    )
    world.db.commit()
    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    assert payload(await call(status, world.ctx))["pedido"] is None


# ---------- contrato do Pack ----------


async def test_pack_exposes_exactly_three_tools_with_json_schema():
    pack = CatalogOrdersPack()
    assert pack.name == "catalog_orders"
    tools = pack.tools()
    assert [t.name for t in tools] == ["buscar_cardapio", "gerenciar_pedido", "status_pedido"]
    for t in tools:
        assert t.input_schema["type"] == "object"
        assert t.description


async def test_system_prompt_section_describes_the_order_flow(world):
    text = CatalogOrdersPack().system_prompt_section(world.ctx)
    for needle in ("buscar_cardapio", "gerenciar_pedido", "status_pedido", "finalizar", "transferir_atendente"):
        assert needle in text
