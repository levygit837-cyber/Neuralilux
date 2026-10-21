"""Executa um Turn para uma Message recebida do Contact.

Ordem: gate de Handoff lido do banco, contexto (Summary + Recent Window), Gateway
do `whatsapp_agent`, loop com as Tools dos Packs da Company, formatação para o
WhatsApp. Quem chama envia `reply_text` (se houver) e cuida do Summary depois do envio.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.orm import Session

from app.agent.contracts import ChatMessage, MessagesClient, Pack, ToolContext
from app.agent.events import TurnEvents
from app.agent.formatting import to_whatsapp
from app.agent.loop import TurnResult, run_turn
from app.agent.prompts import build_system_prompt
from app.agent.tools import ToolRegistry
from app.models.models import Company, Contact, Conversation, Instance

logger = structlog.get_logger()

AGENT_TYPE = "whatsapp_agent"
FALLBACK_REPLY = "Desculpe, tive um problema para responder agora. Pode mandar sua mensagem de novo em instantes?"


def resolve_gateway(agent_type: str) -> tuple[MessagesClient, str, str | None]:
    from app.llm.registry import resolve  # T2

    return resolve(agent_type)


def build_context(db: Session, conversation: Conversation) -> tuple[str | None, list[ChatMessage]]:
    from app.agent.memory import build_context as memory_build_context  # T4

    return memory_build_context(db, conversation)


def packs_for(db: Session, company: Company) -> list[Pack]:
    from app.packs import packs_for_company  # T5

    return packs_for_company(db, company)


def _in_handoff(db: Session, conversation_id: str) -> bool:
    # Lê do banco, não do objeto: um Attendant pode ter assumido depois que a Conversation foi carregada.
    flag = db.query(Conversation.human_in_loop).filter(Conversation.id == conversation_id).scalar()
    return bool(flag)


async def handle_incoming(
    db: Session,
    conversation: Conversation,
    contact: Contact,
    instance: Instance,
    text: str,
) -> TurnResult:
    log = logger.bind(conversation_id=conversation.id, instance_id=instance.id)
    if _in_handoff(db, conversation.id):
        log.info("Conversation in Handoff, Agent stays silent")
        return TurnResult(reply_text=None)

    company = db.get(Company, instance.company_id) if instance.company_id else None
    if company is None:
        log.error("Instance has no Company, Agent cannot run")
        return TurnResult(reply_text=None)

    ctx = ToolContext(
        db=db,
        company_id=company.id,
        instance_id=instance.id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        remote_jid=conversation.remote_jid,
    )
    events = TurnEvents(
        instance_name=instance.name or instance.evolution_instance_id or "",
        conversation_id=conversation.remote_jid,
        request_id=uuid.uuid4().hex,
    )

    await events.thinking_start()
    try:
        summary, history = build_context(db, conversation)
        if not history or history[-1]["role"] != "user":
            # A Message que disparou o Turn ainda não está na janela (ex.: commit pendente).
            history = [*history, {"role": "user", "content": text}]
        packs = packs_for(db, company)
        client, model, effort = resolve_gateway(AGENT_TYPE)
        system = build_system_prompt(company_name=company.name, packs=packs, ctx=ctx, summary=summary)
        result = await run_turn(
            client,
            model,
            system,
            history,
            ToolRegistry.from_packs(packs),
            ctx,
            effort=effort,
            observer=events,
        )
    except Exception:
        log.exception("Turn failed")
        return TurnResult(reply_text=FALLBACK_REPLY)
    finally:
        await events.flush()
        await events.thinking_end()

    reply = to_whatsapp(result.reply_text) if result.reply_text else None
    log.info("Turn finished", steps=result.steps, tools=[call.name for call in result.tool_calls], replied=bool(reply))
    return TurnResult(reply_text=reply or None, tool_calls=result.tool_calls, steps=result.steps)
