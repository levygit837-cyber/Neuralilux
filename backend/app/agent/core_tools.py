"""Tools do núcleo: valem para qualquer Company, independentemente do Pack.

- `info_empresa`: dados cadastrais, horário, Pix, taxas e pedido mínimo, sempre da Company do contexto.
- `transferir_atendente`: Handoff. Abre o Ticket, passa a Conversation para o Attendant e encerra o Turn.
- `buscar_historico`: History Search nas Messages antigas do Contact (`app.agent.memory.search_history`).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.agent.memory import search_history
from app.models.models import Company, Conversation, DeliveryZone, Instance, Message, Ticket

logger = structlog.get_logger()

TRANSFER_MESSAGE = "Vou te passar para um de nossos atendentes. Em instantes alguém continua essa conversa por aqui."
DEFAULT_TIMEZONE = "America/Sao_Paulo"

# Ordem de `datetime.weekday()`: segunda = 0.
DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")

# Ticket.agent_type é obrigatório; o Agent é um só por Company, então o valor é neutro.
HANDOFF_AGENT_TYPE = "whatsapp_agent"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def publish_event(event: dict[str, Any]) -> None:
    from app.services.realtime_event_bus import realtime_event_bus

    await realtime_event_bus.publish(event)


def _ok(data: dict[str, Any]) -> ToolResult:
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def _error(message: str) -> ToolResult:
    return ToolResult(content=json.dumps({"erro": message}, ensure_ascii=False), is_error=True)


# ---------- horário de funcionamento ----------


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _intervals(raw: Any) -> list[tuple[int, int]]:
    return [(_minutes(start), _minutes(end)) for start, end in (raw or [])]


def is_open_at(hours: dict[str, list[list[str]]] | None, local_now: datetime) -> bool | None:
    """True/False se a Company está aberta em `local_now` (já no fuso dela); None se não há horários.

    Intervalo cujo fim é menor ou igual ao início cruza a meia-noite (`["18:00", "02:00"]`);
    fim `"00:00"` significa "até o fim do dia". Dia ausente no dicionário = fechado.
    """
    if not hours:
        return None
    now = local_now.hour * 60 + local_now.minute
    weekday = local_now.weekday()

    for start, end in _intervals(hours.get(DAY_KEYS[weekday])):
        if (start <= now < end) if end > start else (now >= start):
            return True
    # Sobra de ontem: intervalo que cruzou a meia-noite e ainda não terminou.
    for start, end in _intervals(hours.get(DAY_KEYS[(weekday - 1) % 7])):
        if end <= start and now < end:
            return True
    return False


def _company_zone(company: Company) -> ZoneInfo:
    try:
        return ZoneInfo(company.timezone or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown company timezone, using default", company_id=company.id, timezone=company.timezone)
        return ZoneInfo(DEFAULT_TIMEZONE)


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

    zones = (
        ctx.db.query(DeliveryZone)
        .filter(DeliveryZone.company_id == company.id, DeliveryZone.is_active.is_(True))
        .order_by(DeliveryZone.name)
        .all()
    )
    local_now = utc_now().astimezone(_company_zone(company))
    payment_methods = ["pix"] if company.pix_key else []
    payment_methods += ["dinheiro", "cartao"]

    return _ok(
        {
            "nome": company.name,
            "endereco": _format_address(company),
            "telefone": company.phone,
            "horarios": _format_hours(company.business_hours),
            "aberto_agora": is_open_at(company.business_hours, local_now),
            "fuso_horario": company.timezone or DEFAULT_TIMEZONE,
            "formas_pagamento": payment_methods,
            "chave_pix": company.pix_key,
            "pedido_minimo": float(company.minimum_order) if company.minimum_order is not None else None,
            "taxas_entrega": [
                {"zona": z.name, "bairros": list(z.neighborhoods or []), "taxa": float(z.delivery_fee)} for z in zones
            ],
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
    if conversation.human_in_loop and conversation.ticket_id:
        return ToolResult(content=TRANSFER_MESSAGE, ends_turn=True)

    last_incoming = (
        ctx.db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.direction == "incoming", Message.content.isnot(None))
        .order_by(Message.timestamp.desc())
        .first()
    )
    ticket = Ticket(
        conversation_id=conversation.id,
        instance_id=conversation.instance_id,
        contact_id=conversation.contact_id,  # FK de contacts.id, nunca o remote_jid
        agent_type=HANDOFF_AGENT_TYPE,
        reason=reason,
        content=last_incoming.content if last_incoming else reason,
        status="open",
    )
    ctx.db.add(ticket)
    ctx.db.flush()
    conversation.human_in_loop = True
    conversation.human_handoff_reason = reason
    conversation.ticket_id = ticket.id
    ctx.db.commit()

    instance = ctx.db.get(Instance, conversation.instance_id)
    try:
        await publish_event(
            {
                "instance_name": instance.name if instance else None,
                "type": "human_handoff_requested",
                "payload": {
                    "conversation_id": conversation.id,
                    "instance_id": conversation.instance_id,
                    "contact_id": conversation.contact_id,
                    "ticket_id": ticket.id,
                    "reason": reason,
                    "timestamp": utc_now().isoformat(),
                },
            }
        )
    except Exception as exc:  # o Handoff já está gravado; falha de notificação não pode desfazê-lo
        logger.warning("Failed to publish handoff event", ticket_id=ticket.id, error=str(exc))

    return ToolResult(content=TRANSFER_MESSAGE, ends_turn=True)


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
                "Dados da empresa que atende: nome, endereço, telefone, horários de funcionamento, se está "
                "aberta agora, formas de pagamento, chave Pix, taxas de entrega por zona e pedido mínimo. "
                "Use para responder sobre horário, endereço, taxa de entrega ou como pagar."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_info_empresa,
        ),
        Tool(
            name="transferir_atendente",
            description=(
                "Passa a conversa para um atendente humano e encerra o seu turno. Use quando o cliente pedir para "
                "falar com um humano, fizer uma reclamação grave, ou relatar um problema com um pedido já feito. "
                "Não use para dúvidas que você mesmo consegue responder."
            ),
            input_schema={
                "type": "object",
                "properties": {"motivo": {"type": "string", "description": "Por que a conversa precisa de um humano."}},
                "required": ["motivo"],
                "additionalProperties": False,
            },
            handler=_transferir_atendente,
        ),
        Tool(
            name="buscar_historico",
            description=(
                "Busca por palavras nas mensagens antigas deste cliente, fora das mensagens recentes que você já vê. "
                "Use quando o cliente se referir a algo de antes, como 'o pedido de ontem' ou 'aquela pizza que pedi'."
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
