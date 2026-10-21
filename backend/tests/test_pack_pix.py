from decimal import Decimal

import pytest
from pack_helpers import add_item, call, fill_delivery, make_world, order_of, payload, tool_named
from sqlalchemy.exc import IntegrityError

from app.models.models import PaymentRecord
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio

# BR Code gerado com chave, valor, txid, nome e cidade fixos. O CRC (88F4) foi conferido com
# `binascii.crc_hqx(corpo, 0xFFFF)`, independente da implementação do Pack.
EMV_FIXTURE = (
    "00020101021226410014br.gov.bcb.pix0119pix@macedos.example5204000053039865405"
    "95.005802BR5916MACEDOS PIZZARIA6009FORTALEZA6218051420261021ABC123630488F4"
)


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")


def tlv(emv: str) -> dict[str, str]:
    out, i = {}, 0
    while i < len(emv):
        tag, size = emv[i : i + 2], int(emv[i + 2 : i + 4])
        out[tag] = emv[i + 4 : i + 4 + size]
        i += 4 + size
    return out


async def finalize_pix(world, pedido):
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    return await call(pedido, world.ctx, acao="finalizar")


# ---------- EMV ----------


def test_crc16_matches_the_ccitt_false_check_vector():
    assert pix.crc16("123456789") == "29B1"


def test_build_emv_matches_the_known_fixture():
    emv = pix.build_emv(
        key="pix@macedos.example",
        amount=Decimal("95"),
        txid="20261021ABC123",
        merchant_name="Macedos Pizzaria",
        merchant_city="Fortaleza",
    )
    assert emv == EMV_FIXTURE
    assert pix.crc16(EMV_FIXTURE[:-4]) == EMV_FIXTURE[-4:]


def test_merchant_name_and_city_are_ascii_uppercase_and_truncated():
    emv = pix.build_emv(
        key="k@x.co",
        amount=Decimal("1.5"),
        txid="T1",
        merchant_name="Pizzaria São João do Açaí Ltda Muito Longa",
        merchant_city="São Luís do Maranhão",
    )
    fields = tlv(emv)
    assert fields["59"] == "PIZZARIA SAO JOAO DO ACAI"  # 25 caracteres
    assert fields["60"] == "SAO LUIS DO MARAN"[:15]
    assert fields["54"] == "1.50"


def test_emv_field_over_99_chars_raises_pix_error():
    with pytest.raises(pix.PixError):
        pix.build_emv(key="k" * 120, amount=Decimal("1"), txid="T", merchant_name="A", merchant_city="B")


# ---------- finalizar com Pix ----------


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
    assert fields["63"] == pix.crc16(emv[:-4])
    assert "outra@pix.example" not in result.content


async def test_pix_without_company_key_does_not_close_order(world, pedido):
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    world.company.pix_key = None  # chave removida entre a coleta e o fechamento
    world.db.commit()
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "pix" in payload(result)["erro"].lower()
    assert order_of(world).status != "closed"
    assert world.db.query(PaymentRecord).count() == 0


async def test_pix_key_too_long_returns_clear_error_and_keeps_order_open(world, pedido):
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    world.company.pix_key = "k" * 120  # estoura o limite de 99 caracteres do campo EMV
    world.db.commit()

    result = await call(pedido, world.ctx, acao="finalizar")

    assert result.is_error
    message = payload(result)["erro"]
    assert "Pix" in message and "99" in message
    assert order_of(world).status != "closed"
    assert world.db.query(PaymentRecord).count() == 0


# ---------- um Pix por Order ----------


async def test_pix_payment_record_is_deduplicated(world, pedido):
    first = payload(await finalize_pix(world, pedido))
    order = order_of(world)

    again = pix.ensure_payment_record(world.db, order, world.company)

    records = world.db.query(PaymentRecord).all()
    assert len(records) == 1
    assert again.id == records[0].id
    assert records[0].amount == Decimal("95.00")
    assert records[0].qr_code_data == first["pix"]["copia_e_cola"]
    assert records[0].order_id == order.id and records[0].status == "pending"


async def test_unique_index_rejects_a_second_pix_for_the_same_order(world, pedido):
    await finalize_pix(world, pedido)
    order = order_of(world)

    world.db.add(
        PaymentRecord(
            order_id=order.id,
            conversation_id=order.conversation_id,
            amount=order.total_amount,
            pix_key="x@y.z",
            payment_method="pix",
        )
    )
    with pytest.raises(IntegrityError):
        world.db.flush()
    world.db.rollback()
    assert world.db.query(PaymentRecord).count() == 1


async def test_unique_index_only_covers_pix(world, pedido):
    await finalize_pix(world, pedido)
    order = order_of(world)

    world.db.add(
        PaymentRecord(
            order_id=order.id,
            conversation_id=order.conversation_id,
            amount=order.total_amount,
            pix_key="-",
            payment_method="cartao",
        )
    )
    world.db.commit()
    assert world.db.query(PaymentRecord).count() == 2


async def test_ensure_payment_record_recovers_when_a_concurrent_insert_wins(world, pedido, monkeypatch):
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    order = order_of(world)
    order.status = "open"

    # A outra chamada concorrente grava o Pix depois da nossa leitura prévia (que não viu nada).
    winner = PaymentRecord(
        order_id=order.id,
        conversation_id=order.conversation_id,
        amount=Decimal("95.00"),
        pix_key=world.company.pix_key,
        qr_code_data="vencedor",
        payment_method="pix",
    )
    world.db.add(winner)
    world.db.commit()

    real_lookup = pix._existing_record
    calls = []

    def blind_first_lookup(db, order_id):
        calls.append(order_id)
        return None if len(calls) == 1 else real_lookup(db, order_id)

    monkeypatch.setattr(pix, "_existing_record", blind_first_lookup)

    record = pix.ensure_payment_record(world.db, order_of(world), world.company)

    assert len(calls) == 2  # a segunda leitura veio do tratamento do IntegrityError
    assert record.id == winner.id and record.qr_code_data == "vencedor"
    assert world.db.query(PaymentRecord).count() == 1
