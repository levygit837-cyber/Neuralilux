"""Roda um Turn do Agent para a Conversation e envia a resposta, mostrando "digitando…" enquanto o Turn roda."""
import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.config import settings
from app.models import Agent, Contact, Conversation, Instance
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.sender import send_and_persist

logger = structlog.get_logger()


def resolve_default_agent(db: Session, instance: Instance) -> Agent | None:
    """O Agent da Instance: o ligado a ela e, na falta, o Agent ativo da Company."""
    if instance.agent_id:
        agent = db.query(Agent).filter(Agent.id == instance.agent_id, Agent.is_active == True).first()  # noqa: E712
        if agent:
            return agent
    if instance.company_id:
        agent = (
            db.query(Agent)
            .filter(Agent.company_id == instance.company_id, Agent.is_active == True)  # noqa: E712
            .order_by(Agent.created_at, Agent.id)
            .first()
        )
        if agent:
            instance.agent_id = agent.id
            db.commit()
            return agent
    return None


async def _keep_typing(instance_name: str, remote_jid: str) -> None:
    """Renova a presença "composing", que a Evolution encerra sozinha depois do `delay`.

    Falha (Evolution fora, Instance desconectada) é logada uma vez e encerra o laço: a presença é cosmética
    e nunca pode atrasar nem impedir a resposta.
    """
    refresh = settings.TYPING_REFRESH_SECONDS
    loop = asyncio.get_running_loop()
    try:
        while True:
            started = loop.time()
            await evolution_api.send_presence(instance_name, remote_jid, "composing", int(refresh * 1000))
            await asyncio.sleep(max(0.0, refresh - (loop.time() - started)))
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.warning("Typing presence failed, reply continues", instance=instance_name, error=str(error))


@asynccontextmanager
async def typing_indicator(instance_name: str, remote_jid: str) -> AsyncIterator[None]:
    task = asyncio.create_task(_keep_typing(instance_name, remote_jid))
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
    on_replied: Callable[[str], None],
    text: str,
    received_at: datetime,
) -> None:
    """Um Turn com `text` (as Messages do Contact agrupadas, `received_at` a da mais antiga) e o envio da resposta, se houver.

    Abre a própria Session: o Turn roda fora da entrega do webhook, que já terminou e fechou a dela. Nunca levanta; o erro
    fica no log e a próxima Message tenta de novo. `on_replied` é chamado depois da resposta enviada.
    """
    log = logger.bind(instance_id=instance_id, conversation_id=conversation_id)
    db = session_factory()
    try:
        instance = db.get(Instance, instance_id)
        conversation = db.get(Conversation, conversation_id)
        contact = db.get(Contact, contact_id)
        if instance is None or conversation is None or contact is None:
            log.warning("Conversation vanished before the Turn, skipped")
            return

        async with typing_indicator(instance.evolution_instance_id or instance.name, conversation.remote_jid):
            result = await executor.handle_incoming(db, conversation, contact, instance, text, received_at)
        if not result.reply_text:
            log.info("Agent returned no response", steps=result.steps)
            return

        delivered_at = await send_and_persist(db, instance, conversation, contact, result.reply_text)
        executor.reply_delivered(db, instance, conversation, result.turn_id, delivered_at)
        log.info("Agent response sent", steps=result.steps, response_length=len(result.reply_text))
    except Exception:
        log.exception("Unexpected error processing message with agent")
        return
    finally:
        db.close()
    on_replied(conversation_id)
