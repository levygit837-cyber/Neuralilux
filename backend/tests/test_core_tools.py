from datetime import datetime, timezone

import pytest
from pack_helpers import call, make_world, payload, tool_named

from app.agent import core_tools
from app.agent.core_tools import TRANSFER_MESSAGE, core_tools as build_core_tools
from app.models.models import Message, Ticket

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def events(monkeypatch):
    sent: list[dict] = []

    async def publish(event):
        sent.append(event)

    monkeypatch.setattr(core_tools, "publish_event", publish)
    return sent


def tool(name):
    return tool_named(build_core_tools(), name)


async def test_info_empresa_open_now_uses_company_timezone(world, events, monkeypatch):
    info = tool("info_empresa")
    # 2026-10-24 (sábado) 02:30 UTC == sexta 23:30 em Fortaleza (UTC-3): aberto pelo horário de sexta.
    monkeypatch.setattr(core_tools, "utc_now", lambda: datetime(2026, 10, 24, 2, 30, tzinfo=timezone.utc))
    assert payload(await call(info, world.ctx))["aberto_agora"] is True
    # Mesmo instante, mas 03:30 UTC == sábado 00:30 local: sexta já fechou às 00:00.
    monkeypatch.setattr(core_tools, "utc_now", lambda: datetime(2026, 10, 24, 3, 30, tzinfo=timezone.utc))
    assert payload(await call(info, world.ctx))["aberto_agora"] is False


async def test_info_empresa_timezone_changes_the_answer(world, monkeypatch):
    info = tool("info_empresa")
    monkeypatch.setattr(core_tools, "utc_now", lambda: datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc))  # seg 19:00 -03
    assert payload(await call(info, world.ctx))["aberto_agora"] is True
    world.company.timezone = "Asia/Tokyo"  # terça 07:00
    world.db.commit()
    assert payload(await call(info, world.ctx))["aberto_agora"] is False


async def test_info_empresa_fields(world, monkeypatch):
    monkeypatch.setattr(core_tools, "utc_now", lambda: datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc))
    data = payload(await call(tool("info_empresa"), world.ctx))
    assert data["nome"] == "Macedos"
    assert "Rua das Flores" in data["endereco"] and "100" in data["endereco"]
    assert data["telefone"] == "(85) 99999-0000"
    assert data["horarios"]["segunda"] == "18:00-23:00"
    assert data["horarios"]["sexta"] == "18:00-00:00"
    assert data["fuso_horario"] == "America/Fortaleza"
    assert data["formas_pagamento"] == ["pix", "dinheiro", "cartao"]
    assert data["chave_pix"] == "pix@macedos.example"
    assert data["pedido_minimo"] == 30.0
    assert data["taxas_entrega"] == [{"zona": "Centro", "bairros": ["Centro", "Aldeota"], "taxa": 5.0}]


async def test_info_empresa_is_scoped_to_context_company(world):
    data = payload(await call(tool("info_empresa"), world.ctx))
    assert "Outra Pizzaria" not in str(data) and "outra@pix.example" not in str(data)
    assert all(z["zona"] not in ("Praia", "Legada") for z in data["taxas_entrega"])


async def test_info_empresa_without_hours_or_pix(db):
    world = make_world(db, pix_key=None)
    world.company.business_hours = None
    db.commit()
    data = payload(await call(tool("info_empresa"), world.ctx))
    assert data["aberto_agora"] is None
    assert "pix" not in data["formas_pagamento"] and data["chave_pix"] is None


# ---------- transferir_atendente ----------


async def test_transfer_creates_ticket_with_contact_fk_and_flags_conversation(world, events):
    world.db.add(
        Message(
            instance_id=world.instance.id,
            conversation_id=world.conversation.id,
            remote_jid=world.contact.remote_jid,
            direction="incoming",
            content="meu pedido veio errado!",
            timestamp=datetime.now(timezone.utc),
        )
    )
    world.db.commit()

    result = await call(tool("transferir_atendente"), world.ctx, motivo="Pedido veio errado")
    assert result.ends_turn is True and not result.is_error
    assert result.content == TRANSFER_MESSAGE

    world.db.expire_all()
    ticket = world.db.query(Ticket).one()
    assert ticket.contact_id == world.contact.id  # e não o remote_jid
    assert ticket.contact_id != world.contact.remote_jid
    assert ticket.conversation_id == world.conversation.id
    assert ticket.instance_id == world.instance.id
    assert ticket.agent_type == "whatsapp_agent"
    assert ticket.reason == "Pedido veio errado"
    assert ticket.content == "meu pedido veio errado!"
    assert ticket.status == "open"

    world.db.refresh(world.conversation)
    assert world.conversation.human_in_loop is True
    assert world.conversation.ticket_id == ticket.id
    assert world.conversation.human_handoff_reason == "Pedido veio errado"


async def test_transfer_falls_back_to_reason_when_no_incoming_message(world, events):
    await call(tool("transferir_atendente"), world.ctx, motivo="Reclamação grave")
    assert world.db.query(Ticket).one().content == "Reclamação grave"


async def test_transfer_is_idempotent_per_conversation(world, events):
    first = await call(tool("transferir_atendente"), world.ctx, motivo="a")
    second = await call(tool("transferir_atendente"), world.ctx, motivo="b")
    assert first.ends_turn and second.ends_turn
    assert world.db.query(Ticket).count() == 1
    assert len(events) == 1


async def test_transfer_requires_reason(world, events):
    result = await call(tool("transferir_atendente"), world.ctx, motivo="   ")
    assert result.is_error and not result.ends_turn
    assert world.db.query(Ticket).count() == 0


async def test_transfer_survives_event_bus_failure(world, monkeypatch):
    async def boom(event):
        raise ConnectionError("redis down")

    monkeypatch.setattr(core_tools, "publish_event", boom)
    result = await call(tool("transferir_atendente"), world.ctx, motivo="x")
    assert result.ends_turn and not result.is_error
    assert world.db.query(Ticket).count() == 1


async def test_transfer_description_lists_triggers_instead_of_keywords():
    description = tool("transferir_atendente").description.lower()
    for trigger in ("humano", "reclama", "pedido"):
        assert trigger in description


# ---------- buscar_historico ----------


async def test_buscar_historico_with_no_match_returns_empty_list(world):
    result = await call(tool("buscar_historico"), world.ctx, consulta="lasanha")
    assert not result.is_error
    assert payload(result)["resultados"] == []


async def test_buscar_historico_blank_query_is_error(world):
    assert (await call(tool("buscar_historico"), world.ctx, consulta="  ")).is_error


# ---------- contrato ----------


async def test_core_exposes_exactly_three_tools():
    tools = build_core_tools()
    assert [t.name for t in tools] == ["info_empresa", "transferir_atendente", "buscar_historico"]
    assert tools[0].input_schema["properties"] == {}
    assert tools[1].input_schema["required"] == ["motivo"]
    assert tools[2].input_schema["required"] == ["consulta"]


async def test_six_tools_in_total():
    from app.packs.catalog_orders.pack import CatalogOrdersPack

    names = [t.name for t in build_core_tools()] + [t.name for t in CatalogOrdersPack().tools()]
    assert len(names) == len(set(names)) == 6


async def test_buscar_historico_uses_memory_search_scoped_to_contact(world):
    from app.models.models import Contact, Conversation

    def message(conversation, jid, text):
        return Message(
            instance_id=world.instance.id,
            conversation_id=conversation.id,
            remote_jid=jid,
            direction="incoming",
            message_type="text",
            content=text,
            timestamp=datetime.now(timezone.utc),
        )

    other = Contact(instance_id=world.instance.id, phone_number="5585911112222", remote_jid="5585911112222@s.whatsapp.net")
    world.db.add(other)
    world.db.flush()
    other_conversation = Conversation(instance_id=world.instance.id, contact_id=other.id, remote_jid=other.remote_jid)
    world.db.add(other_conversation)
    world.db.flush()
    world.db.add_all(
        [
            message(world.conversation, world.contact.remote_jid, "quero a pizza toscana de ontem"),
            message(other_conversation, other.remote_jid, "pizza toscana do outro cliente"),
        ]
    )
    world.db.commit()

    result = await call(tool("buscar_historico"), world.ctx, consulta="toscana")
    snippets = [r["snippet"] for r in payload(result)["resultados"]]
    assert snippets == ["quero a pizza toscana de ontem"]
