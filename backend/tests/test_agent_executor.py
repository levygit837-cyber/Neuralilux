"""handle_incoming: gate de Handoff, Turn completo e falhas, contra Gateway falso."""

import pytest

from app.agent import executor
from app.agent.contracts import Tool, ToolResult
from app.models.models import Company, Contact, Conversation, Instance
from tests.agent_fakes import FakeMessagesClient, FakePack, reply, text, tool_use


@pytest.fixture
def turn_setup(db):
    company = Company(name="Pizzaria Teste")
    db.add(company)
    db.flush()
    instance = Instance(name="loja", evolution_instance_id="evo-loja", company_id=company.id)
    db.add(instance)
    db.flush()
    contact = Contact(
        instance_id=instance.id,
        phone_number="5511999999999",
        remote_jid="5511999999999@s.whatsapp.net",
        name="Cliente",
    )
    db.add(contact)
    db.flush()
    conversation = Conversation(instance_id=instance.id, contact_id=contact.id, remote_jid=contact.remote_jid)
    db.add(conversation)
    db.commit()
    return db, conversation, contact, instance


@pytest.fixture
def agent(monkeypatch):
    """Liga o executor a um Gateway falso, a uma memória vazia e a um Pack com uma Tool."""
    state = {"client": FakeMessagesClient([]), "tool_calls": [], "summary": None}

    async def buscar(ctx, args):
        state["tool_calls"].append((ctx, args))
        return ToolResult(content="Pizza Toscana R$ 45,90")

    pack = FakePack(
        "catalogo",
        [Tool(name="buscar_cardapio", description="Busca", input_schema={"type": "object"}, handler=buscar)],
        section="Seção do Pack",
    )
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (state["client"], "fake-model", "low"))
    monkeypatch.setattr(executor, "build_context", lambda db, conversation: (state["summary"], []))
    monkeypatch.setattr(executor, "packs_for", lambda db, company: [pack])
    return state


@pytest.mark.asyncio
async def test_conversation_em_handoff_nao_responde_nem_chama_o_modelo(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    # Um Attendant assumiu por outra Session depois que a Conversation foi carregada.
    db.query(Conversation).filter(Conversation.id == conversation.id).update({"human_in_loop": True})
    db.commit()
    db.expire_all()
    conversation.__dict__["human_in_loop"] = False  # objeto em memória desatualizado

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")

    assert result.reply_text is None
    assert agent["client"].requests == []


@pytest.mark.asyncio
async def test_turn_com_tool_devolve_resposta_formatada_para_whatsapp(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    agent["summary"] = "Cliente já pediu calabresa antes."
    agent["client"].script = [
        reply(tool_use("buscar_cardapio", {"consulta": "pizza toscana"}, "toolu_1")),
        reply(text("Temos **Pizza Toscana** por R$ 1.250,00")),
    ]

    result = await executor.handle_incoming(db, conversation, contact, instance, "Tem pizza toscana?")

    assert result.reply_text == "Temos *Pizza Toscana* por R$ 1.250,00"
    assert [call.name for call in result.tool_calls] == ["buscar_cardapio"]
    ctx, args = agent["tool_calls"][0]
    assert args == {"consulta": "pizza toscana"}
    assert (ctx.company_id, ctx.instance_id, ctx.conversation_id, ctx.contact_id) == (
        instance.company_id,
        instance.id,
        conversation.id,
        contact.id,
    )
    first = agent["client"].requests[0]
    assert first.messages == [{"role": "user", "content": "Tem pizza toscana?"}]
    assert first.effort == "low"
    assert "Pizzaria Teste" in first.system
    assert "Seção do Pack" in first.system
    assert "Cliente já pediu calabresa antes." in first.system


@pytest.mark.asyncio
async def test_falha_do_gateway_devolve_mensagem_generica_sem_debug(turn_setup, agent, monkeypatch):
    db, conversation, contact, instance = turn_setup

    def no_gateway(agent_type):
        raise RuntimeError("Nenhum Gateway atribuído a 'whatsapp_agent'")

    monkeypatch.setattr(executor, "resolve_gateway", no_gateway)

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")

    assert result.reply_text == executor.FALLBACK_REPLY
    assert "[Debug" not in result.reply_text
    assert "Gateway" not in result.reply_text


@pytest.mark.asyncio
async def test_instance_sem_company_nao_responde(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    instance.company_id = None
    db.commit()

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")

    assert result.reply_text is None
    assert agent["client"].requests == []
