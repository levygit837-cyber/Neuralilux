"""Roda um Turn do Agent para a Conversation e envia a resposta, mostrando "digitando…" enquanto o Turn roda."""
import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.config import settings
from app.models import Agent, Company, Contact, Conversation, Instance
from app.packs.registry import packs_for
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.sender import send_and_persist
from app.whatsapp.turn_batcher import Group

logger = structlog.get_logger()

# Como o Turn terminou, para o runner gravar o estado das Messages (`turn_state`).
REPLIED = "replied"  # a resposta saiu (inclui a resposta fixa de erro do executor)
NO_REPLY = "no_reply"  # o Agent decidiu não responder (Handoff, por exemplo)
GONE = "gone"  # a Conversation ou o Agent sumiram antes do Turn
FAILED = "failed"  # nada saiu por erro (Gateway, Evolution, banco): a Message continua pendente


async def _keep_typing(
    instance_name: str,
    remote_jid: str,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Renova a presença "composing", que a Evolution encerra sozinha depois do `delay`.

    Falha (Evolution fora, Instance desconectada) é logada uma vez e encerra o laço: a presença é cosmética
    e nunca pode atrasar nem impedir a resposta.
    """
    refresh = settings.TYPING_REFRESH_SECONDS
    try:
        while True:
            started = monotonic()
            await evolution_api.send_presence(instance_name, remote_jid, "composing", int(refresh * 1000))
            await sleep(max(0.0, refresh - (monotonic() - started)))
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.warning("Typing presence failed, reply continues", instance=instance_name, error=str(error))


@asynccontextmanager
async def typing_indicator(
    instance_name: str,
    remote_jid: str,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> AsyncIterator[None]:
    task = asyncio.create_task(_keep_typing(instance_name, remote_jid, sleep, monotonic))
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def run_agent_turn(
    session_factory: Callable[[], Session],
    instance_id: str,
    conversation_id: str,
    contact_id: str,
    agent_id: str,
    on_replied: Callable[[str], None],
    group: Group,
) -> str:
    """Um Turn com as Messages do Contact agrupadas em `group` e o envio da resposta, se houver.

    Devolve como terminou: `REPLIED`, `NO_REPLY`, `GONE` ou `FAILED`.

    `agent_id` é o Agent que o consumer resolveu para a Instance; o Turn o carrega na Session dele e o passa ao executor.
    Abre a própria Session: o Turn roda fora da entrega do webhook, que já terminou e fechou a dela. Nunca levanta; o erro
    fica no log (`FAILED`) e a recuperação tenta de novo. `on_replied` é chamado depois da resposta enviada.
    """
    log = logger.bind(instance_id=instance_id, conversation_id=conversation_id)
    db = session_factory()
    try:
        instance = db.get(Instance, instance_id)
        conversation = db.get(Conversation, conversation_id)
        contact = db.get(Contact, contact_id)
        agent = db.get(Agent, agent_id)
        if instance is None or conversation is None or contact is None or agent is None:
            log.warning("Conversation vanished before the Turn, skipped")
            return GONE
        company = db.get(Company, instance.company_id) if instance.company_id else None
        packs = packs_for(company) if company else []

        async with typing_indicator(instance.evolution_instance_id or instance.name, conversation.remote_jid):
            result = await executor.handle_incoming(
                db,
                conversation,
                contact,
                instance,
                group.text,
                group.received_at,
                message_ids=group.message_ids,
                deferred_ids=group.deferred_ids,
                agent=agent,
                packs=packs,
            )
        if not result.reply_text:
            log.info("Agent returned no response", steps=result.steps)
            return NO_REPLY

        delivered_at = await send_and_persist(db, instance, conversation, contact, result.reply_text)
        executor.reply_delivered(db, conversation, packs, result.turn_id, delivered_at)
        log.info("Agent response sent", steps=result.steps, response_length=len(result.reply_text))
    except Exception:
        log.exception("Unexpected error processing message with agent")
        return FAILED
    finally:
        db.close()
    on_replied(conversation_id)
    return REPLIED
