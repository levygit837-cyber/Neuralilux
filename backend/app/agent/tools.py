"""Registry das Tools que o Agent pode chamar num Turn.

Junta as Tools de todos os Packs, expõe os schemas no formato Messages e executa
um `tool_use`: valida o input com JSON Schema, chama o handler e devolve o
`tool_result`. Nenhuma exceção de handler sai daqui: vira `is_error` com mensagem
genérica e o erro real vai para o log.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import structlog
from jsonschema import Draft202012Validator

from app.agent.contracts import Pack, Tool, ToolContext, ToolResultBlock, ToolUseBlock

logger = structlog.get_logger()

GENERIC_TOOL_ERROR = "A ferramenta falhou ao executar. Não repita a mesma chamada; siga sem ela ou ofereça um Attendant."


@dataclass(frozen=True)
class ToolCall:
    """Um `tool_use` executado num Turn, com o `tool_result` devolvido ao modelo."""

    name: str
    input: dict[str, Any]
    result: ToolResultBlock
    ends_turn: bool = False

    @property
    def is_error(self) -> bool:
        return bool(self.result.get("is_error"))


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        self._validators: dict[str, Draft202012Validator] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Tool duplicada entre Packs: {tool.name}")
            Draft202012Validator.check_schema(tool.input_schema)
            self._tools[tool.name] = tool
            self._validators[tool.name] = Draft202012Validator(tool.input_schema)

    @classmethod
    def from_packs(cls, packs: Iterable[Pack]) -> ToolRegistry:
        return cls(tool for pack in packs for tool in pack.tools())

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in self._tools.values()
        ]

    async def execute(self, ctx: ToolContext, block: ToolUseBlock) -> ToolCall:
        name = block["name"]
        args = block.get("input") or {}
        tool = self._tools.get(name)
        if tool is None:
            return _error(block, f"Tool desconhecida: {name}.")

        problems = sorted(self._validators[name].iter_errors(args), key=lambda e: list(e.path))
        if problems:
            detail = "; ".join(_describe(problem) for problem in problems)
            return _error(block, f"Argumentos inválidos para {name}: {detail}")

        try:
            outcome = await tool.handler(ctx, args)
        except Exception:
            logger.exception(
                "Tool handler failed",
                tool_name=name,
                conversation_id=ctx.conversation_id,
                tool_use_id=block["id"],
            )
            return _error(block, GENERIC_TOOL_ERROR)

        result: ToolResultBlock = {"type": "tool_result", "tool_use_id": block["id"], "content": outcome.content}
        if outcome.is_error:
            result["is_error"] = True
        return ToolCall(name=name, input=args, result=result, ends_turn=outcome.ends_turn)


def _describe(problem: Any) -> str:
    where = ".".join(str(part) for part in problem.absolute_path)
    return f"{where}: {problem.message}" if where else problem.message


def _error(block: ToolUseBlock, message: str) -> ToolCall:
    return ToolCall(
        name=block["name"],
        input=block.get("input") or {},
        result={"type": "tool_result", "tool_use_id": block["id"], "content": message, "is_error": True},
    )
