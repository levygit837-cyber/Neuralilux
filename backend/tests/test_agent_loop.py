"""run_turn: o loop do Agent contra um FakeMessagesClient roteirizado."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.agent.loop import MAX_STEPS_FALLBACK_REPLY, run_turn
from app.agent.tools import GENERIC_TOOL_ERROR, ToolRegistry
from app.models.models import Company
from tests.agent_fakes import FakeMessagesClient, FakePack, reply, text, tool_use

CTX = ToolContext(
    db=MagicMock(),
    company_id="company-1",
    instance_id="instance-1",
    conversation_id="conversation-1",
    contact_id="contact-1",
    remote_jid="5511999999999@s.whatsapp.net",
)
HISTORY = [{"role": "user", "content": "Tem pizza toscana?"}]
OPEN_SCHEMA = {"type": "object"}


def _registry(**handlers):
    tools = [
        Tool(name=name, description=f"tool {name}", input_schema=OPEN_SCHEMA, handler=handler)
        for name, handler in handlers.items()
    ]
    return ToolRegistry.from_packs([FakePack("p", tools)])


def _returning(content, **flags):
    calls = []

    async def handler(ctx, args):
        calls.append(args)
        return ToolResult(content=content, **flags)

    handler.calls = calls
    return handler


async def _run(client, registry, **kwargs):
    return await run_turn(client, "fake-model", "SYSTEM", HISTORY, registry, CTX, **kwargs)


@pytest.mark.asyncio
async def test_turn_sem_tools_devolve_o_texto_do_modelo():
    client = FakeMessagesClient([reply(text("Olá! Como posso ajudar?"))])
    registry = _registry(buscar_cardapio=_returning("x"))

    result = await _run(client, registry, effort="low")

    assert result.reply_text == "Olá! Como posso ajudar?"
    assert result.tool_calls == []
    assert result.steps == 1
    request = client.requests[0]
    assert request.system == "SYSTEM"
    assert request.model == "fake-model"
    assert request.effort == "low"
    assert request.messages == HISTORY
    assert [schema["name"] for schema in request.tools] == ["buscar_cardapio"]


@pytest.mark.asyncio
async def test_um_tool_use_e_executado_e_o_resultado_volta_ao_modelo():
    buscar = _returning("Pizza Toscana R$ 45,90")
    assistant = [text("Vou ver."), tool_use("buscar_cardapio", {"consulta": "pizza toscana"}, "toolu_1")]
    client = FakeMessagesClient([reply(*assistant), reply(text("Temos sim, R$ 45,90."))])

    result = await _run(client, _registry(buscar_cardapio=buscar))

    assert result.reply_text == "Temos sim, R$ 45,90."
    assert result.steps == 2
    assert buscar.calls == [{"consulta": "pizza toscana"}]
    assert [call.name for call in result.tool_calls] == ["buscar_cardapio"]
    assert client.requests[1].messages == [
        *HISTORY,
        {"role": "assistant", "content": assistant},
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "Pizza Toscana R$ 45,90"}],
        },
    ]


@pytest.mark.asyncio
async def test_varios_tool_use_executam_em_ordem_e_voltam_juntos():
    order = []

    def tracking(label):
        async def handler(ctx, args):
            order.append(label)
            return ToolResult(content=label)

        return handler

    client = FakeMessagesClient(
        [
            reply(tool_use("info_empresa", {}, "toolu_a"), tool_use("buscar_cardapio", {}, "toolu_b")),
            reply(tool_use("gerenciar_pedido", {"acao": "ver"}, "toolu_c")),
            reply(text("Pronto.")),
        ]
    )
    registry = _registry(
        info_empresa=tracking("info"), buscar_cardapio=tracking("busca"), gerenciar_pedido=tracking("pedido")
    )

    result = await _run(client, registry)

    assert order == ["info", "busca", "pedido"]
    assert result.steps == 3
    assert result.reply_text == "Pronto."
    second_round_results = client.requests[1].messages[-1]["content"]
    assert [block["tool_use_id"] for block in second_round_results] == ["toolu_a", "toolu_b"]


@pytest.mark.asyncio
async def test_tool_com_erro_volta_como_is_error_e_o_turn_continua():
    async def boom(ctx, args):
        raise RuntimeError("db caiu")

    client = FakeMessagesClient(
        [reply(tool_use("buscar_cardapio", {}, "toolu_1")), reply(text("Tive um problema, já te chamo um atendente."))]
    )

    result = await _run(client, _registry(buscar_cardapio=boom))

    assert result.reply_text == "Tive um problema, já te chamo um atendente."
    assert result.tool_calls[0].is_error is True
    returned = client.requests[1].messages[-1]["content"][0]
    assert returned == {"type": "tool_result", "tool_use_id": "toolu_1", "content": GENERIC_TOOL_ERROR, "is_error": True}


@pytest.mark.asyncio
async def test_ends_turn_para_sem_chamar_o_modelo_de_novo_e_responde_a_mensagem_da_tool():
    transferir = _returning("Vou te passar para um atendente.", ends_turn=True)
    depois = _returning("não deveria rodar")
    client = FakeMessagesClient(
        [
            reply(
                tool_use("transferir_atendente", {"motivo": "reclamação"}, "toolu_1"),
                tool_use("gerenciar_pedido", {}, "toolu_2"),
            )
        ]
    )

    result = await _run(client, _registry(transferir_atendente=transferir, gerenciar_pedido=depois))

    assert len(client.requests) == 1
    assert result.reply_text == "Vou te passar para um atendente."
    assert result.steps == 1
    assert depois.calls == []
    assert [call.name for call in result.tool_calls] == ["transferir_atendente"]


@pytest.mark.asyncio
async def test_max_steps_faz_chamada_final_com_schemas_e_ignora_tool_use_dela():
    buscar = _returning("nada")
    client = FakeMessagesClient(
        [
            reply(tool_use("buscar_cardapio", {}, "toolu_1")),
            reply(tool_use("buscar_cardapio", {}, "toolu_2")),
            reply(text("Não achei, quer outra opção?"), tool_use("buscar_cardapio", {}, "toolu_3")),
        ]
    )

    result = await _run(client, _registry(buscar_cardapio=buscar), max_steps=2)

    assert result.reply_text == "Não achei, quer outra opção?"
    assert result.steps == 3
    assert len(result.tool_calls) == 2
    assert len(buscar.calls) == 2
    final = client.requests[-1]
    # O histórico tem tool_use/tool_result: o request continua precisando das definições das Tools.
    assert [schema["name"] for schema in final.tools] == ["buscar_cardapio"]
    last_user = final.messages[-1]
    assert last_user["role"] == "user"
    assert last_user["content"][0] == {"type": "tool_result", "tool_use_id": "toolu_2", "content": "nada"}
    assert last_user["content"][-1]["type"] == "text"


@pytest.mark.asyncio
async def test_max_steps_sem_texto_na_chamada_final_responde_mensagem_fixa():
    client = FakeMessagesClient(
        [
            reply(tool_use("buscar_cardapio", {}, "toolu_1")),
            reply(tool_use("buscar_cardapio", {}, "toolu_2")),  # a chamada final também só pede Tool
        ]
    )

    result = await _run(client, _registry(buscar_cardapio=_returning("nada")), max_steps=1)

    assert result.reply_text == MAX_STEPS_FALLBACK_REPLY
    assert result.steps == 2
    assert len(result.tool_calls) == 1


@pytest.mark.asyncio
async def test_resposta_sem_texto_significa_nao_responder():
    client = FakeMessagesClient([reply(text("   "))])

    result = await _run(client, _registry())

    assert result.reply_text is None


@pytest.mark.asyncio
async def test_historico_do_chamador_nao_e_alterado():
    history = [{"role": "user", "content": "oi"}]
    client = FakeMessagesClient([reply(tool_use("info_empresa", {}, "toolu_1")), reply(text("Oi!"))])

    await run_turn(client, "m", "S", history, _registry(info_empresa=_returning("dados")), CTX)

    assert history == [{"role": "user", "content": "oi"}]


@pytest.mark.asyncio
async def test_flush_que_falha_numa_tool_nao_quebra_a_proxima_tool_do_turn(db):
    db.add(Company(id="company-dup", name="Original"))
    db.commit()

    async def grava_duplicado(ctx, args):
        ctx.db.add(Company(id="company-dup", name="Duplicada"))
        ctx.db.flush()  # IntegrityError: chave primária repetida
        return ToolResult(content="não chega aqui")

    async def consulta(ctx, args):
        return ToolResult(content=ctx.db.get(Company, "company-dup").name)

    client = FakeMessagesClient(
        [
            reply(tool_use("grava", {}, "toolu_1"), tool_use("consulta", {}, "toolu_2")),
            reply(text("ok")),
        ]
    )

    result = await run_turn(
        client, "m", "S", HISTORY, _registry(grava=grava_duplicado, consulta=consulta), replace(CTX, db=db)
    )

    failed, queried = result.tool_calls
    assert failed.is_error
    assert queried.result == {"type": "tool_result", "tool_use_id": "toolu_2", "content": "Original"}
