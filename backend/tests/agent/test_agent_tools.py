"""ToolRegistry: schemas no formato Messages e execução de tool_use."""

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.agent.tools import ToolRegistry

CTX = ToolContext(
    db=MagicMock(),
    company_id="company-1",
    instance_id="instance-1",
    conversation_id="conversation-1",
    contact_id="contact-1",
    remote_jid="5511999999999@s.whatsapp.net",
)

ITEM_SCHEMA = {
    "type": "object",
    "properties": {"consulta": {"type": "string"}},
    "required": ["consulta"],
    "additionalProperties": False,
}


@dataclass
class FakePack:
    name: str
    pack_tools: list[Tool]

    def tools(self) -> list[Tool]:
        return self.pack_tools

    def system_prompt_section(self, ctx: ToolContext) -> str:
        return ""

    def on_session_start(self, db, conversation) -> None:
        return None


def _tool(name, handler, schema=ITEM_SCHEMA, description="desc"):
    return Tool(name=name, description=description, input_schema=schema, handler=handler)


def _use(name, input, id="toolu_1"):
    return {"type": "tool_use", "id": id, "name": name, "input": input}


async def _echo(ctx, args):
    return ToolResult(content=f"{ctx.company_id}:{args['consulta']}")


def test_schemas_no_formato_messages_de_todos_os_packs():
    registry = ToolRegistry.from_packs(
        [
            FakePack("core", [_tool("info_empresa", _echo, {"type": "object"}, "Dados da Company")]),
            FakePack("catalog", [_tool("buscar_cardapio", _echo, ITEM_SCHEMA, "Busca itens")]),
        ]
    )

    assert registry.schemas() == [
        {"name": "info_empresa", "description": "Dados da Company", "input_schema": {"type": "object"}},
        {"name": "buscar_cardapio", "description": "Busca itens", "input_schema": ITEM_SCHEMA},
    ]


def test_nome_de_tool_duplicado_entre_packs_e_recusado():
    with pytest.raises(ValueError, match="buscar_cardapio"):
        ToolRegistry.from_packs(
            [
                FakePack("a", [_tool("buscar_cardapio", _echo)]),
                FakePack("b", [_tool("buscar_cardapio", _echo)]),
            ]
        )


@pytest.mark.asyncio
async def test_execute_devolve_tool_result_do_handler():
    registry = ToolRegistry.from_packs([FakePack("p", [_tool("buscar_cardapio", _echo)])])

    call = await registry.execute(CTX, _use("buscar_cardapio", {"consulta": "pizza"}, id="toolu_9"))

    assert call.result == {"type": "tool_result", "tool_use_id": "toolu_9", "content": "company-1:pizza"}
    assert call.ends_turn is False


@pytest.mark.asyncio
async def test_input_invalido_vira_erro_sem_chamar_o_handler():
    called = []

    async def handler(ctx, args):
        called.append(args)
        return ToolResult(content="ok")

    registry = ToolRegistry.from_packs([FakePack("p", [_tool("buscar_cardapio", handler)])])

    call = await registry.execute(CTX, _use("buscar_cardapio", {"consulta": 42}))

    assert called == []
    assert call.result["is_error"] is True
    assert "consulta" in call.result["content"]


@pytest.mark.asyncio
async def test_excecao_do_handler_vira_erro_generico_sem_vazar_detalhe():
    async def boom(ctx, args):
        raise RuntimeError("senha do banco: hunter2")

    registry = ToolRegistry.from_packs([FakePack("p", [_tool("buscar_cardapio", boom)])])

    call = await registry.execute(CTX, _use("buscar_cardapio", {"consulta": "x"}))

    assert call.result["is_error"] is True
    assert "hunter2" not in call.result["content"]
    assert "RuntimeError" not in call.result["content"]
    assert call.ends_turn is False


@pytest.mark.asyncio
async def test_tool_desconhecida_vira_erro():
    registry = ToolRegistry.from_packs([])

    call = await registry.execute(CTX, _use("apagar_tudo", {}))

    assert call.result["is_error"] is True
    assert "apagar_tudo" in call.result["content"]


@pytest.mark.asyncio
async def test_ends_turn_e_erro_do_handler_sao_repassados():
    async def transfer(ctx, args):
        return ToolResult(content="Transferido", ends_turn=True)

    async def refuse(ctx, args):
        return ToolResult(content="Item indisponível", is_error=True)

    registry = ToolRegistry.from_packs(
        [FakePack("p", [_tool("transferir_atendente", transfer), _tool("gerenciar_pedido", refuse)])]
    )

    transferred = await registry.execute(CTX, _use("transferir_atendente", {"consulta": "x"}))
    refused = await registry.execute(CTX, _use("gerenciar_pedido", {"consulta": "x"}))

    assert transferred.ends_turn is True
    assert "is_error" not in transferred.result
    assert refused.result["is_error"] is True
    assert refused.result["content"] == "Item indisponível"
