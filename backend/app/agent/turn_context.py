"""Bloco de contexto por Turn: o que muda de um Turn para o seguinte.

O system prompt e as Tools têm de ser idênticos byte a byte entre Turns da mesma Company, senão o prefix cache
do servidor de inferência não vale (issue #42). Tudo que é por Turn vai aqui, num bloco delimitado no início da
última mensagem `user` do Turn: hora local, contexto de cada Pack (`Pack.turn_context`) e Summary.

Para acrescentar um item do núcleo ao bloco (ex.: estado aberto/fechado da Company), some uma seção em
`build_turn_context`; para um item do ramo, o Pack o devolve em `turn_context`. O system não muda.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.agent.contracts import ChatMessage, Pack, ToolContext

CONTEXT_TAG = "contexto_do_atendimento"
OPEN_TAG = f"<{CONTEXT_TAG}>"
CLOSE_TAG = f"</{CONTEXT_TAG}>"

# Qualquer "<contexto_do_atendimento" ou "</ contexto_do_atendimento", em qualquer caixa, mesmo sem o ">".
_TAG_START = re.compile(rf"<(\s*/?\s*{CONTEXT_TAG})", re.IGNORECASE)


def neutralize(text: str) -> str:
    """Troca o "<" que abriria ou fecharia o bloco por "‹": o texto do Contact não forja o bloco."""
    return _TAG_START.sub(r"‹\1", text)


def build_turn_context(*, time_context: str | None, packs: Iterable[Pack], ctx: ToolContext, summary: str | None) -> str:
    """O bloco do Turn: hora, contexto dos Packs e Summary, nessa ordem. Vazio se não há nada a dizer."""
    sections = [time_context or ""]
    sections.extend(pack.turn_context(ctx) for pack in packs)
    if summary and summary.strip():
        sections.append(f"Resumo da conversa até aqui (mensagens antigas):\n{summary.strip()}")
    body = neutralize("\n\n".join(section.strip() for section in sections if section.strip()))
    return f"{OPEN_TAG}\n{body}\n{CLOSE_TAG}" if body else ""


def attach_turn_context(history: list[ChatMessage], block: str) -> list[ChatMessage]:
    """Devolve `history` com `block` no início da última mensagem `user` (nova mensagem `user` se a última não é).

    Todo texto do histórico passa por `neutralize`; o bloco, não.
    """
    messages: list[ChatMessage] = [
        {"role": m["role"], "content": neutralize(m["content"])} if isinstance(m["content"], str) else m
        for m in history
    ]
    if not block:
        return messages
    last = messages[-1] if messages else None
    if last is not None and last["role"] == "user" and isinstance(last["content"], str):
        messages[-1] = {"role": "user", "content": f"{block}\n\n{last['content']}"}
    else:
        messages.append({"role": "user", "content": block})
    return messages
