"""O loop de um Turn do Agent (ADR 0001).

Chama o modelo; enquanto ele pedir `tool_use`, executa todas as Tools em ordem,
anexa a resposta do assistant e os `tool_result` e chama de novo. Para em
`end_turn` (ou qualquer outro `stop_reason`), numa Tool com `ends_turn` ou ao
atingir `max_steps`; neste caso faz uma última chamada pedindo a resposta. Essa
chamada ainda leva os schemas das Tools (o histórico tem `tool_use`/`tool_result`
e o protocolo exige as definições), mas qualquer `tool_use` nela é ignorado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agent.contracts import (
    DEFAULT_MAX_TOKENS,
    ChatMessage,
    ContentBlock,
    MessagesClient,
    MessagesRequest,
    MessagesResponse,
    ToolContext,
    ToolUseBlock,
)
from app.agent.tools import ToolCall, ToolRegistry
from app.llm.retry import RetryBudget

FINAL_ANSWER_INSTRUCTION = (
    "Limite de ferramentas atingido neste atendimento. Responda agora ao cliente com o que você já sabe, "
    "sem chamar ferramentas."
)
# Resposta fixa quando a chamada final de `max_steps` volta sem texto: o cliente não pode ficar sem retorno.
MAX_STEPS_FALLBACK_REPLY = "Desculpe, não consegui concluir agora. Pode me dizer de novo o que você precisa?"


class TurnObserver(Protocol):
    """Recebe o ciclo de vida de cada Tool do Turn (eventos para o frontend)."""

    def tool_started(self, block: ToolUseBlock) -> Any: ...

    def tool_finished(self, handle: Any, call: ToolCall) -> None: ...


@dataclass(frozen=True)
class TurnResult:
    reply_text: str | None  # None: o Agent não responde neste Turn
    tool_calls: list[ToolCall] = field(default_factory=list)
    steps: int = 0
    # Turn cuja resposta pode ter mostrado algo ao Contact; o consumer o devolve a `executor.reply_delivered`
    # depois do envio. None: nada a confirmar (falha, resposta fixa de erro ou Handoff).
    turn_id: str | None = None


async def run_turn(
    client: MessagesClient,
    model: str,
    system: str,
    history: list[ChatMessage],
    registry: ToolRegistry,
    ctx: ToolContext,
    *,
    max_steps: int = 6,
    effort: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float | None = None,
    observer: TurnObserver | None = None,
) -> TurnResult:
    messages: list[ChatMessage] = list(history)
    tools = registry.schemas()
    tool_calls: list[ToolCall] = []
    steps = 0
    # Um orçamento para o Turn inteiro: as até 7 chamadas ao modelo dividem os retries, não cada uma os seus.
    budget = RetryBudget.for_turn()

    def request() -> MessagesRequest:
        # `messages` é a mesma lista que o loop vai anexando; cada chamada vê o estado atual.
        return MessagesRequest(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            effort=effort,
            temperature=temperature,
            retry_budget=budget,
        )

    while True:
        response = await client.create(request())
        steps += 1
        uses = [block for block in response.content if block["type"] == "tool_use"]
        if response.stop_reason != "tool_use" or not uses:
            return TurnResult(reply_text=_reply_text(response), tool_calls=tool_calls, steps=steps)

        results: list[ContentBlock] = []
        for block in uses:
            handle = observer.tool_started(block) if observer else None
            call = await registry.execute(ctx, block)
            if observer:
                observer.tool_finished(handle, call)
            tool_calls.append(call)
            results.append(call.result)
            if call.ends_turn:
                return TurnResult(reply_text=_clean(call.result["content"]), tool_calls=tool_calls, steps=steps)

        messages.append({"role": "assistant", "content": response.content})
        if steps >= max_steps:
            results.append({"type": "text", "text": FINAL_ANSWER_INSTRUCTION})
            messages.append({"role": "user", "content": results})
            final = await client.create(request())
            # Só o texto conta: um tool_use aqui não é executado. Sem texto, resposta fixa.
            reply_text = _reply_text(final) or MAX_STEPS_FALLBACK_REPLY
            return TurnResult(reply_text=reply_text, tool_calls=tool_calls, steps=steps + 1)
        messages.append({"role": "user", "content": results})


def _reply_text(response: MessagesResponse) -> str | None:
    return _clean("\n\n".join(block["text"] for block in response.content if block["type"] == "text"))


def _clean(text: str) -> str | None:
    text = text.strip()
    return text or None
