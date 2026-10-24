"""
Saída do Agent: envia a resposta pela Evolution, grava a Message `from_me` e avisa a UI ao vivo.
"""
import time
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.status_events import publish_message, touch_conversation

logger = structlog.get_logger()

# Respostas do Agent enviadas sem id da Evolution: o eco `fromMe` delas chega depois pelo webhook e NÃO é um
# Attendant escrevendo. Fica na memória do worker (quem envia é quem consome o eco) e expira sozinho.
ECHO_TTL_SECONDS = 120.0
_unmatched_sends: dict[tuple[str, str], list[tuple[str, float]]] = {}


def _remember_send_without_id(instance_id: str, remote_jid: str, text: str) -> None:
    now = time.monotonic()
    key = (instance_id, remote_jid)
    pending = [(t, at) for t, at in _unmatched_sends.get(key, []) if now - at < ECHO_TTL_SECONDS]
    pending.append((text.strip(), now))
    _unmatched_sends[key] = pending


def claim_agent_echo(instance_id: str, remote_jid: str, text: str | None) -> bool:
    """True se `text` é o eco de uma resposta do Agent enviada sem id; consome essa marca (vale uma vez)."""
    key = (instance_id, remote_jid)
    now = time.monotonic()
    pending = [(t, at) for t, at in _unmatched_sends.get(key, []) if now - at < ECHO_TTL_SECONDS]
    wanted = (text or "").strip()
    for index, (sent, _at) in enumerate(pending):
        if sent == wanted:
            del pending[index]
            _store(key, pending)
            return True
    _store(key, pending)
    return False


def _store(key: tuple[str, str], pending: list[tuple[str, float]]) -> None:
    if pending:
        _unmatched_sends[key] = pending
    else:
        _unmatched_sends.pop(key, None)


async def send_and_persist(
    db: Session, instance: Instance, conversation: Conversation, contact: Contact, text: str, *, sent_by: str | None = None
) -> datetime:
    """Envia pela Evolution e grava a resposta como Message `from_me`, com o id devolvido.

    Devolve quando a resposta saiu. Falha no envio levanta; falha só ao gravar não desfaz o envio.

    Assim o eco do webhook (mesmo id) é descartado pelo dedup, e a UI recebe a resposta aqui.

    `sent_by="system"` marca um aviso da API (não é o Agent nem um Attendant). Esse aviso é sempre gravado, mesmo sem
    id da Evolution (`message_id` NULL): o eco depois o reconhece no banco (`system_notice.adopt_echo`), entre processos.
    """
    instance_name = instance.evolution_instance_id or instance.name
    response = await evolution_api.send_text_message(
        instance_name=instance_name,
        remote_jid=conversation.remote_jid,
        text=text,
    )
    sent_id = ((response or {}).get("key") or {}).get("id")
    if not sent_id:
        logger.warning("Evolution did not return a message id", sent_by=sent_by)
        if sent_by is None:
            # Sem id não há como deduplicar o eco; deixa o eco gravar a Message.
            _remember_send_without_id(instance.id, conversation.remote_jid, text)
            return datetime.now(timezone.utc)

    timestamp = datetime.now(timezone.utc)
    try:
        db.add(
            Message(
                instance_id=instance.id,
                conversation_id=conversation.id,
                remote_jid=conversation.remote_jid,
                message_id=sent_id,
                message_type="text",
                content=text,
                direction="outgoing",
                status="sent",
                is_from_me=True,
                sent_by=sent_by,
                timestamp=timestamp,
            )
        )
        touch_conversation(conversation, text, timestamp, unread=False)
        db.commit()
    except Exception:
        # A resposta já saiu; falhar ao gravar não pode reenviar nem derrubar o Turn.
        db.rollback()
        logger.exception("Failed to persist the Agent reply", message_id=sent_id)
        return timestamp
    await publish_message(conversation, contact, sent_id, text, timestamp, True)
    return timestamp
