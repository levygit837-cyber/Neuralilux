"""handle_incoming: gate de Handoff, Turn completo e falhas, contra Gateway falso e memória real."""

from datetime import datetime, timedelta, timezone

import pytest

from app.agent import executor
from app.agent.contracts import DEFAULT_MAX_TOKENS, Tool, ToolResult
from app.core import database
from app.models import Agent, Company, Contact, Conversation, ConversationMemorySummary, Instance, Message
from tests.agent_fakes import FakeMessagesClient, FakePack, reply, text, tool_use
from tests.conftest import TestingSessionLocal


def _message(db, conversation, content, direction, minutes_ago):
    message = Message(
        instance_id=conversation.instance_id,
        conversation_id=conversation.id,
        remote_jid=conversation.remote_jid,
        message_type="text",
        content=content,
        direction=direction,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(message)
    db.commit()
    return message


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
    """Liga o executor a um Gateway falso e a um Pack com Tools; a memória é a real, sobre o SQLite."""
    state = {"client": FakeMessagesClient([]), "tool_calls": []}

    async def buscar(ctx, args):
        state["tool_calls"].append((ctx, args))
        return ToolResult(content="Pizza Toscana R$ 45,90")

    tools = [Tool(name="buscar_cardapio", description="Busca", input_schema={"type": "object"}, handler=buscar)]
    pack = FakePack("catalogo", tools, section="Seção do Pack")
    state["add_tool"] = lambda name, handler: tools.append(
        Tool(name=name, description=name, input_schema={"type": "object"}, handler=handler)
    )
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (state["client"], "fake-model", "low"))
    monkeypatch.setattr(executor, "pack_for_company", lambda company: pack)
    return state


def _attendant_takes_over(conversation_id):
    # Outra Session, como o painel do Attendant faria.
    other = TestingSessionLocal()
    try:
        other.query(Conversation).filter(Conversation.id == conversation_id).update({"human_in_loop": True})
        other.commit()
    finally:
        other.close()


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
async def test_turn_com_tool_usa_a_memoria_e_devolve_resposta_formatada(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    old = _message(db, conversation, "Quero uma calabresa", "incoming", minutes_ago=30)
    db.add(
        ConversationMemorySummary(
            conversation_id=conversation.id,
            summary="Cliente já pediu calabresa antes.",
            covered_until_message_id=old.id,
            message_count=1,
        )
    )
    _message(db, conversation, "Anotado!", "outgoing", minutes_ago=29)
    incoming = _message(db, conversation, "Tem pizza toscana?", "incoming", minutes_ago=0)
    agent["client"].script = [
        reply(tool_use("buscar_cardapio", {"consulta": "pizza toscana"}, "toolu_1")),
        reply(text("Temos **Pizza Toscana** por R$ 1.250,00")),
    ]

    result = await executor.handle_incoming(
        db, conversation, contact, instance, "Tem pizza toscana?", message_ids=[incoming.id]
    )

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
    assert first.messages == [
        {"role": "user", "content": "Quero uma calabresa"},
        {"role": "assistant", "content": "Anotado!"},
        {"role": "user", "content": "Tem pizza toscana?"},
    ]
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


@pytest.mark.asyncio
async def test_texto_atual_entra_mesmo_com_message_anterior_do_contact_sem_resposta(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    _message(db, conversation, "Oi, tudo bem?", "incoming", minutes_ago=5)  # ficou sem resposta
    agent["client"].script = [reply(text("Temos sim!"))]

    # A Message atual ainda não foi gravada quando o Turn começa.
    await executor.handle_incoming(db, conversation, contact, instance, "Tem pizza toscana?")

    assert agent["client"].requests[0].messages == [{"role": "user", "content": "Oi, tudo bem?\nTem pizza toscana?"}]


@pytest.mark.asyncio
async def test_falha_no_turn_desfaz_a_session_para_quem_chama(turn_setup, agent, monkeypatch):
    db, conversation, contact, instance = turn_setup
    company_id = instance.company_id

    def broken_context(session, conv):
        session.add(Company(id=company_id, name="Duplicada"))
        session.flush()  # IntegrityError: chave primária repetida

    monkeypatch.setattr(executor, "build_context", broken_context)

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")

    assert result.reply_text == executor.FALLBACK_REPLY
    # O consumer continua usando a mesma Session depois do Turn.
    assert db.get(Company, company_id).name == "Pizzaria Teste"


@pytest.mark.asyncio
async def test_attendant_que_assume_durante_o_turn_cala_o_agent(turn_setup, agent):
    db, conversation, contact, instance = turn_setup

    async def lenta(ctx, args):
        _attendant_takes_over(conversation.id)
        return ToolResult(content="dados")

    agent["add_tool"]("consulta_lenta", lenta)
    agent["client"].script = [reply(tool_use("consulta_lenta", {}, "toolu_1")), reply(text("Resposta do Agent"))]

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")

    assert result.reply_text is None


@pytest.mark.asyncio
async def test_tool_que_transfere_ainda_envia_a_mensagem_de_transferencia(turn_setup, agent):
    db, conversation, contact, instance = turn_setup

    async def transferir(ctx, args):
        _attendant_takes_over(conversation.id)
        return ToolResult(content="Vou te passar para um atendente.", ends_turn=True)

    # Nome próprio: `transferir_atendente` já vem do CorePack e o registry recusa duplicata.
    agent["add_tool"]("transferir_teste", transferir)
    agent["client"].script = [reply(tool_use("transferir_teste", {}, "toolu_1"))]

    result = await executor.handle_incoming(db, conversation, contact, instance, "quero falar com alguém")

    assert result.reply_text == "Vou te passar para um atendente."


@pytest.mark.asyncio
async def test_refresh_summary_usa_session_propria_e_falha_nao_afeta_a_resposta(turn_setup, agent, monkeypatch):
    db, conversation, contact, instance = turn_setup
    opened = []

    def session_factory():
        session = TestingSessionLocal()
        opened.append(session)
        return session

    seen = {}

    async def failing_refresh(session, client, model, conv):
        seen["session"] = session
        seen["conversation_id"] = conv.id
        raise RuntimeError("Gateway caiu no resumo")

    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(executor, "maybe_refresh_summary", failing_refresh)
    agent["client"].script = [reply(text("Oi! Como posso ajudar?"))]

    result = await executor.handle_incoming(db, conversation, contact, instance, "oi")
    await executor.refresh_summary(conversation.id)  # não levanta

    assert result.reply_text == "Oi! Como posso ajudar?"
    assert seen["conversation_id"] == conversation.id
    assert seen["session"] is opened[0]
    assert seen["session"] is not db


# ---------- hora local e tempo desde a última Message no prompt ----------

NOW = datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc)  # quinta, 20:30 em Fortaleza (-03)


def _at(db, conversation, content, direction, moment):
    message = Message(
        instance_id=conversation.instance_id,
        conversation_id=conversation.id,
        remote_jid=conversation.remote_jid,
        message_type="text",
        content=content,
        direction=direction,
        timestamp=moment,
    )
    db.add(message)
    db.commit()
    return message


async def _prompt(turn_setup, agent, monkeypatch, timezone_name="America/Fortaleza"):
    db, conversation, contact, instance = turn_setup
    db.get(Company, instance.company_id).timezone = timezone_name
    db.commit()
    monkeypatch.setattr(executor, "utc_now", lambda: NOW)
    agent["client"].script = [reply(text("ok"))]
    newest = db.query(Message).filter_by(conversation_id=conversation.id, direction="incoming").order_by(
        Message.timestamp.desc()
    ).first()
    await executor.handle_incoming(db, conversation, contact, instance, "oi", message_ids=[newest.id])
    return agent["client"].requests[0].system


@pytest.mark.asyncio
async def test_prompt_traz_data_e_hora_no_fuso_da_company(turn_setup, agent, monkeypatch):
    db, conversation, *_ = turn_setup
    _at(db, conversation, "oi", "incoming", NOW)

    system = await _prompt(turn_setup, agent, monkeypatch)

    assert "quinta-feira, 22/10/2026, 20:30 (fuso America/Fortaleza)" in system


@pytest.mark.asyncio
async def test_prompt_muda_de_dia_conforme_o_fuso_da_company(turn_setup, agent, monkeypatch):
    db, conversation, *_ = turn_setup
    _at(db, conversation, "oi", "incoming", NOW)

    system = await _prompt(turn_setup, agent, monkeypatch, "Asia/Tokyo")

    assert "sexta-feira, 23/10/2026, 08:30 (fuso Asia/Tokyo)" in system


@pytest.mark.asyncio
async def test_prompt_diz_ha_quanto_tempo_foi_a_mensagem_anterior(turn_setup, agent, monkeypatch):
    db, conversation, *_ = turn_setup
    _at(db, conversation, "quero uma toscana", "incoming", NOW - timedelta(hours=2, minutes=10))
    _at(db, conversation, "anotado", "outgoing", NOW - timedelta(hours=2, minutes=9))
    _at(db, conversation, "oi", "incoming", NOW)

    system = await _prompt(turn_setup, agent, monkeypatch)

    assert "foi há 2 h 9 min" in system
    assert "novo atendimento" not in system


@pytest.mark.asyncio
async def test_prompt_marca_a_volta_depois_de_pausa_longa_e_a_janela_so_tem_a_session_atual(
    turn_setup, agent, monkeypatch
):
    db, conversation, *_ = turn_setup
    _at(db, conversation, "quero uma toscana", "incoming", NOW - timedelta(hours=7, minutes=5))
    _at(db, conversation, "anotado", "outgoing", NOW - timedelta(hours=7, minutes=4))
    _at(db, conversation, "oi", "incoming", NOW)
    conversation.session_started_at = NOW
    db.commit()

    system = await _prompt(turn_setup, agent, monkeypatch)

    assert "foi há 7 h 4 min" in system
    assert "novo atendimento depois de uma pausa longa" in system
    assert agent["client"].requests[0].messages == [{"role": "user", "content": "oi"}]


@pytest.mark.asyncio
async def test_prompt_da_primeira_mensagem_nao_inventa_mensagem_anterior(turn_setup, agent, monkeypatch):
    db, conversation, *_ = turn_setup
    _at(db, conversation, "oi", "incoming", NOW)

    system = await _prompt(turn_setup, agent, monkeypatch)

    assert "primeira mensagem deste cliente" in system
    assert "mensagem anterior" not in system


@pytest.mark.asyncio
async def test_turn_usa_temperatura_e_limite_de_tokens_do_agent_da_company(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    db.add(Agent(name="Atendente", system_prompt="p", company_id=instance.company_id, temperature=0.2, max_tokens=700))
    db.commit()
    agent["client"].script = [reply(text("Olá!"))]

    await executor.handle_incoming(db, conversation, contact, instance, "oi")

    request = agent["client"].requests[0]
    assert (request.temperature, request.max_tokens) == (0.2, 700)


@pytest.mark.asyncio
async def test_company_sem_agent_cadastrado_usa_os_padroes(turn_setup, agent):
    db, conversation, contact, instance = turn_setup
    agent["client"].script = [reply(text("Olá!"))]

    await executor.handle_incoming(db, conversation, contact, instance, "oi")

    request = agent["client"].requests[0]
    assert (request.temperature, request.max_tokens) == (None, DEFAULT_MAX_TOKENS)
