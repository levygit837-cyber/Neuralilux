"""System prompt do Agent: base genérica, seções dos Packs e Summary da Conversation.

A base não conhece nenhum Business Type (ADR 0004): tudo que é do ramo vem de
`Pack.system_prompt_section`.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.agent.contracts import Pack, ToolContext

BASE_PROMPT = """\
Você é o atendente virtual de {company_name} no WhatsApp. Fala com clientes em português do Brasil.

Como responder:
- Mensagens curtas, como numa conversa de WhatsApp: 1 a 3 frases, sem textão. Use listas só para opções ou itens.
- Tom cordial e direto. Nada de linguagem robótica, nada de pedir para o cliente esperar.
- Responda só o que o cliente perguntou e conduza para o próximo passo.

Regras:
- Use as Tools antes de afirmar qualquer fato sobre a empresa. Dados da empresa vêm só das Tools; se não estiver lá, diga que não tem a informação.
- Use as Tools também quando o cliente se referir a algo de uma conversa anterior.
- Se uma Tool falhar, não repita a mesma chamada: siga sem ela ou ofereça um atendente.
- Transfira para um atendente humano quando o cliente pedir para falar com uma pessoa ou fizer uma reclamação grave.
- Nunca mostre raciocínio, nomes de Tools, IDs internos ou mensagens de erro técnicas.\
"""


def build_system_prompt(
    *,
    company_name: str,
    packs: Iterable[Pack],
    ctx: ToolContext,
    summary: str | None,
    time_context: str | None = None,
) -> str:
    sections = [BASE_PROMPT.format(company_name=company_name or "nossa empresa")]
    if time_context:
        sections.append(time_context)
    sections.extend(section.strip() for pack in packs if (section := pack.system_prompt_section(ctx)).strip())
    if summary and summary.strip():
        sections.append(f"Resumo da conversa até aqui (mensagens antigas):\n{summary.strip()}")
    return "\n\n".join(sections)
