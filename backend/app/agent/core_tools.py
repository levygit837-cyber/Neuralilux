"""Tools do núcleo: valem para qualquer Company, independentemente do Pack.

- `info_empresa`: nome, endereço, telefone, horários e se está aberta agora, sempre da Company do contexto.
- `transferir_atendente`: Handoff. Abre o Ticket, passa a Conversation para o Attendant e encerra o Turn.
- `buscar_historico`: History Search nas Messages antigas do Contact (`app.agent.memory.search_history`).

Nada aqui conhece um ramo (ADR 0004): o que é de um negócio específico fica no Pack do Business Type.
"""

from __future__ import annotations

import json
from typing import Any

from app.agent.business_hours import DAY_KEYS, DAY_LABELS, describe_opening, is_open_at, next_opening
from app.agent import clock
from app.agent.clock import DEFAULT_TIMEZONE, company_zone
from app.agent.contracts import Tool, ToolContext, ToolResult
from app.agent.memory import search_history
from app.models import Company, Conversation, Instance
from app.realtime.publish import publish_event
from app.services.handoff_service import open_handoff


TRANSFER_MESSAGE = "Vou te passar para um de nossos atendentes. Em instantes alguém continua essa conversa por aqui."
AFTER_HOURS_MESSAGE = (
    "Nosso atendimento humano está fora do horário agora. Um atendente continua essa conversa {when}."
)
AFTER_HOURS_NO_WINDOW_MESSAGE = (
    "Nosso atendimento humano está fora do horário agora. Um atendente continua essa conversa assim que possível."
)


def _ok(data: dict[str, Any]) -> ToolResult:
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def _error(message: str) -> ToolResult:
    return ToolResult(content=json.dumps({"erro": message}, ensure_ascii=False), is_error=True)


def _format_address(company: Company) -> str | None:
    street = ", ".join(p for p in (company.address_street, company.address_number) if p)
    city = "/".join(p for p in (company.address_city, company.address_state) if p)
    parts = [p for p in (street, company.address_complement, company.address_neighborhood, city) if p]
    return " - ".join(parts) or None


def _format_hours(hours: dict[str, list[list[str]]] | None) -> dict[str, str] | None:
    if not hours:
        return None
    return {
        label: ", ".join(f"{start}-{end}" for start, end in hours.get(key) or []) or "fechado"
        for key, label in zip(DAY_KEYS, DAY_LABELS)
    }


# ---------- info_empresa ----------


async def _info_empresa(ctx: ToolContext, _args: dict[str, Any]) -> ToolResult:
    company = ctx.db.get(Company, ctx.company_id)
    if company is None:
        return _error("Empresa não encontrada.")

    local_now = clock.utc_now().astimezone(company_zone(company))

    return _ok(
        {
            "nome": company.name,
            "endereco": _format_address(company),
            "telefone": company.phone,
            "horarios": _format_hours(company.business_hours),
            "aberto_agora": is_open_at(company.business_hours, local_now),
            "fuso_horario": company.timezone or DEFAULT_TIMEZONE,
        }
    )


# ---------- transferir_atendente ----------


async def _transferir_atendente(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    reason = str(args.get("motivo") or "").strip()
    if not reason:
        return _error("Informe o motivo da transferência.")

    conversation = ctx.db.get(Conversation, ctx.conversation_id)
    if conversation is None:
        return _error("Conversa não encontrada.")
    company = ctx.db.get(Company, ctx.company_id)
    farewell = _handoff_reply(company, str(args.get("frase_empatica") or ""))
    if conversation.human_in_loop and conversation.ticket_id:
        return ToolResult(content=farewell, ends_turn=True)

    ticket = open_handoff(ctx.db, conversation, reason)
    if ticket is None:  # outra requisição abriu o Handoff no meio: o Turn termina do mesmo jeito
        return ToolResult(content=farewell, ends_turn=True)
    instance = ctx.db.get(Instance, conversation.instance_id)
    await publish_event(  # o Handoff já está gravado; falha de notificação só loga (`publish_event`)
        {
            "instance_name": instance.name if instance else None,
            "type": "human_handoff_requested",
            "payload": {
                "conversation_id": conversation.id,
                "instance_id": conversation.instance_id,
                "contact_id": conversation.contact_id,
                "ticket_id": ticket.id,
                "reason": reason,
                "timestamp": clock.utc_now().isoformat(),
            },
        }
    )

    return ToolResult(content=farewell, ends_turn=True)


def _handoff_reply(company: Company | None, empathy: str) -> str:
    """Resposta final do Turn de Handoff: frase empática do Agent + quando haverá atendimento humano."""
    return " ".join(part for part in (_single_line(empathy), _handoff_availability(company)) if part)


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _handoff_availability(company: Company | None) -> str:
    """Fixa em horário comercial; fora dele, informa a próxima janela de atendimento."""
    if company is None or not company.business_hours:
        return TRANSFER_MESSAGE
    local_now = clock.utc_now().astimezone(company_zone(company))
    if is_open_at(company.business_hours, local_now):
        return TRANSFER_MESSAGE
    opening = next_opening(company.business_hours, local_now)
    if opening is None:
        return AFTER_HOURS_NO_WINDOW_MESSAGE
    return AFTER_HOURS_MESSAGE.format(when=describe_opening(opening, local_now))


# ---------- buscar_historico ----------


async def _buscar_historico(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    query = str(args.get("consulta") or "").strip()
    if not query:
        return _error("Informe o que buscar no histórico.")
    return _ok({"resultados": search_history(ctx.db, ctx.contact_id, ctx.instance_id, query)})


# ---------- registro ----------


def core_tools() -> list[Tool]:
    """As 3 Tools do núcleo."""
    return [
        Tool(
            name="info_empresa",
            description=(
                "Dados da empresa que atende: nome, endereço, telefone, horários de funcionamento e se está "
                "aberta agora. Use para responder sobre horário, endereço ou telefone."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_info_empresa,
        ),
        Tool(
            name="transferir_atendente",
            description=(
                "Passa a conversa para um atendente humano e encerra o seu turno. Use quando o cliente pedir para "
                "falar com um humano, fizer uma reclamação grave, ou relatar um problema com algo que já foi "
                "combinado. Não use para dúvidas que você mesmo consegue responder. Antes de "
                "transferir, escreva em frase_empatica uma frase curta e acolhedora ao cliente, coerente com o "
                "motivo (peça desculpas numa reclamação; confirme que vai chamar uma pessoa). Não prometa "
                "prazo nem horário: o sistema acrescenta quando haverá atendimento humano."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "motivo": {"type": "string", "description": "Por que a conversa precisa de um humano."},
                    "frase_empatica": {
                        "type": "string",
                        "description": "Uma ou duas frases empáticas ao cliente, em português, sem prazo nem horário.",
                    },
                },
                "required": ["motivo"],
                "additionalProperties": False,
            },
            handler=_transferir_atendente,
        ),
        Tool(
            name="buscar_historico",
            description=(
                "Busca por palavras nas mensagens antigas deste cliente, fora das mensagens recentes que você já vê. "
                "Use quando o cliente se referir a algo de antes, como 'aquilo que combinamos ontem'."
            ),
            input_schema={
                "type": "object",
                "properties": {"consulta": {"type": "string", "description": "Palavras a procurar."}},
                "required": ["consulta"],
                "additionalProperties": False,
            },
            handler=_buscar_historico,
        ),
    ]
