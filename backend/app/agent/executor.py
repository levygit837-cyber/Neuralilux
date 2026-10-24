"""Executa um Turn para uma Message recebida do Contact.

Ordem: gate de Handoff lido do banco, contexto (Summary + Recent Window da Session atual, hora local), Gateway
do `whatsapp_agent` (system estável; o que muda por Turn vai no bloco da última mensagem `user`), loop com as Tools dos Packs da Company, formatação para o
WhatsApp e nova leitura do Handoff antes de devolver a resposta. Quem chama envia
`reply_text` (se houver) e depois agenda `refresh_summary` fora do caminho da resposta.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from app.agent.clock import opening_notice, time_context, utc_now
from app.agent.contracts import DEFAULT_MAX_TOKENS, ChatMessage, Pack, ToolContext
from app.agent.delivery import notify_reply_delivered
from app.agent.events import TurnEvents
from app.agent.formatting import to_whatsapp
from app.agent.loop import TurnResult, run_turn
from app.agent.memory import build_context, maybe_refresh_summary
from app.agent.prompts import build_system_prompt
from app.agent.sessions import previous_message_at
from app.agent.tools import ToolRegistry
from app.agent.turn_context import attach_turn_context, build_turn_context
from app.core import database
from app.core.config import settings
from app.llm.registry import resolve as resolve_gateway
from app.models import Agent, Company, Contact, Conversation, Instance

logger = structlog.get_logger()

AGENT_TYPE = "whatsapp_agent"
FALLBACK_REPLY = "Desculpe, tive um problema para responder agora. Pode mandar sua mensagem de novo em instantes?"


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
    received_at: datetime | None = None,
    message_ids: Sequence[str] = (),
    deferred_ids: Sequence[str] = (),
    *,
    agent: Agent | None,
    packs: Sequence[Pack],
) -> TurnResult:
    """Um Turn para `text`, as Messages do Contact já gravadas em `message_ids` (juntas, uma por linha).

    Essas Messages saem da Recent Window e voltam como o fim do histórico, uma vez só e na ordem em que chegaram.
    `deferred_ids` são Messages já gravadas que ficam para o Turn seguinte: este Turn não as vê.
    `agent` é o Agent já resolvido para a Instance (`agent_service.resolve_turn_agent`): dele vêm as instruções da
    Company, `max_tokens` e `temperature`. O executor não escolhe Agent; `None` roda com os padrões.
    `packs` são os Packs do Turn (núcleo + ramo da Company), escolhidos por quem chama: o executor não conhece ramos.
    """
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
        trigger_at=received_at or utc_now(),  # quando chegou a Message que dispara o Turn
    )
    events = TurnEvents(
        instance_id=instance.id,
        conversation_id=conversation.id,
        request_id=uuid.uuid4().hex,
    )

    # O prazo do Turn inteiro conta daqui, mas só é armado em volta do loop (Gateway e Tools): o resto é síncrono.
    deadline = asyncio.timeout_at(asyncio.get_running_loop().time() + settings.TURN_TIMEOUT_SECONDS)
    try:
        # Antes de qualquer `await`: Message que chega depois fica para o Turn seguinte, não entra neste histórico.
        summary, history = build_context(db, conversation, exclude_ids=[*message_ids, *deferred_ids])
        await events.thinking_start()
        history = _with_incoming(history, text)
        client, model, effort = resolve_gateway(AGENT_TYPE)
        now = utc_now()
        when = time_context(company, now, previous_message_at(db, conversation.id, message_ids, deferred_ids), conversation.session_started_at)
        system = build_system_prompt(
            company_name=company.name,
            packs=packs,
            ctx=ctx,
            company_instructions=agent.system_prompt if agent else None,
        )
        block = build_turn_context(
            time_context=when, opening=opening_notice(company, now), packs=packs, ctx=ctx, summary=summary
        )
        history = attach_turn_context(history, block)
        async with deadline:
            result = await run_turn(
                client,
                model,
                system,
                history,
                ToolRegistry.from_packs(packs),
                ctx,
                effort=effort,
                max_tokens=(agent.max_tokens if agent else None) or DEFAULT_MAX_TOKENS,
                temperature=agent.temperature if agent else None,
                observer=events,
            )
    except Exception:
        # A Session do Turn pode ter ficado inválida (flush que falhou) ou com transação aberta (Tool cancelada pelo
        # prazo); quem chama ainda vai usá-la. Sem `turn_id` no retorno, nenhum Pack valida nada do Turn (Recap).
        db.rollback()
        if deadline.expired():
            log.error("Turn timed out", timeout_seconds=settings.TURN_TIMEOUT_SECONDS)
        else:
            log.exception("Turn failed")
        return TurnResult(reply_text=FALLBACK_REPLY)
    finally:
        await events.flush()
        await events.thinking_end()

    ended_by_tool = any(call.ends_turn for call in result.tool_calls)
    if not ended_by_tool and _in_handoff(db, conversation.id):
        # Um Attendant assumiu enquanto o modelo respondia: a resposta do Agent não sai.
        log.info("Conversation entered Handoff during the Turn, reply dropped")
        return TurnResult(reply_text=None, tool_calls=result.tool_calls, steps=result.steps)

    reply = to_whatsapp(result.reply_text) if result.reply_text else None
    log.info("Turn finished", steps=result.steps, tools=[call.name for call in result.tool_calls], replied=bool(reply))
    # Handoff encerrou o Turn: a resposta é a frase de transferência, não pode ter mostrado nada do Pack.
    turn_id = None if ended_by_tool else ctx.turn_id
    return TurnResult(reply_text=reply or None, tool_calls=result.tool_calls, steps=result.steps, turn_id=turn_id)


def reply_delivered(
    db: Session, conversation: Conversation, packs: Iterable[Pack], turn_id: str | None, at: datetime
) -> None:
    """Avisa os Packs que a resposta do Turn `turn_id` foi enviada ao Contact. Chamar só depois do envio."""
    if turn_id is None:
        return
    try:
        notify_reply_delivered(db, conversation, packs, turn_id, at)
    except Exception:
        # A resposta já saiu; sem a marca de entrega o Pack só pede a confirmação de novo (falha segura).
        db.rollback()
        logger.exception("Reply delivery hook failed", conversation_id=conversation.id, turn_id=turn_id)


def _with_incoming(history: list[ChatMessage], text: str) -> list[ChatMessage]:
    """Põe `text` (as Messages que disparam o Turn) como a última entrada `user`.

    A Recent Window vem sem elas. Se termina em `user` (Message anterior sem resposta), o texto se junta a essa
    entrada; senão vira uma entrada nova. A primeira entrada continua `user`, como `build_context` garante.
    """
    incoming = text.strip()
    if not incoming:
        return history
    if history and history[-1]["role"] == "user" and isinstance(history[-1]["content"], str):
        return [*history[:-1], {"role": "user", "content": f"{history[-1]['content']}\n{incoming}"}]
    return [*history, {"role": "user", "content": incoming}]


async def refresh_summary(conversation_id: str) -> None:
    """Atualiza o Summary da Conversation, depois que a resposta já foi enviada.

    Abre a própria Session, separada da do Turn. O worker roda num event loop persistente e agenda esta
    função como task de fundo, rastreada e aguardada no shutdown. Falhas só vão para o log.
    """
    db = database.SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            return
        client, model, _effort = resolve_gateway(AGENT_TYPE)
        await maybe_refresh_summary(db, client, model, conversation)
    except Exception:
        db.rollback()
        logger.exception("Summary refresh failed", conversation_id=conversation_id)
    finally:
        db.close()
