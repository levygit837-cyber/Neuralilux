"""
Saída da API: envia pela Evolution, grava a Message `from_me` e avisa a UI ao vivo.

É o único caminho de envio: o Agent (Turn), o aviso de status do Order e o painel (HTTP e Socket.IO, via `panel_send`)
passam por `send_and_persist`.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.conversation_lock import SAVE, conversation_lock, jid_scope
from app.core.threads import settle
from app.models import Contact, Conversation, Instance, Message
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.status_events import publish_message, touch_conversation

logger = structlog.get_logger()


@dataclass(frozen=True)
class Recipient:
    """Para quem a saída vai, só com escalares: o envio roda no event loop e não pode ler ORM expirado (ADR 0009)."""

    instance_id: str
    instance_name: str  # nome da Instance na Evolution
    conversation_id: str
    contact_id: str
    remote_jid: str

    @classmethod
    def of(cls, instance: Instance, conversation: Conversation, contact: Contact) -> "Recipient":
        """Copia os escalares de objetos já carregados (chamar antes de qualquer commit ou rollback da Session)."""
        return cls(
            instance_id=instance.id,
            instance_name=instance.evolution_instance_id or instance.name,
            conversation_id=conversation.id,
            contact_id=contact.id,
            remote_jid=conversation.remote_jid,
        )

    @classmethod
    def from_conversation(cls, instance: Instance, conversation: Conversation) -> "Recipient":
        """Como `of`, para quem só tem a Conversation: o Contact é o `contact_id` dela (sem carregar a linha)."""
        return cls(
            instance_id=instance.id,
            instance_name=instance.evolution_instance_id or instance.name,
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
            remote_jid=conversation.remote_jid,
        )


@dataclass(frozen=True)
class Sent:
    """A saída que a Evolution aceitou. `message_id` é NULL se a Evolution não devolveu id."""

    message_id: str | None
    timestamp: datetime
    saved: bool  # False: a Message não foi gravada (o eco do webhook a cria)


def _persist_reply(
    db: Session, to: Recipient, sent_id: str | None, text: str, sent_by: str | None, timestamp: datetime
) -> tuple[Conversation, Contact]:
    """Grava a Message `from_me` e confirma. Bloqueante: roda em thread. Devolve Conversation e Contact recarregados
    depois do commit (que expira os atributos) para o `publish_message` não ir ao banco de dentro do event loop."""
    conversation = db.get(Conversation, to.conversation_id)
    contact = db.get(Contact, to.contact_id)
    db.add(
        Message(
            instance_id=to.instance_id,
            conversation_id=to.conversation_id,
            remote_jid=to.remote_jid,
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
    db.refresh(conversation)
    db.refresh(contact)
    return conversation, contact


async def send_and_persist(db: Session, to: Recipient, text: str, *, sent_by: str | None = None) -> Sent:
    """Envia pela Evolution e grava a saída como Message `from_me`, com o id devolvido.

    Devolve quando a saída saiu. Falha no envio levanta; falha só ao gravar não desfaz o envio nem levanta: devolve
    `Sent(saved=False)`, sem publicar. A Message então não existe até o eco do webhook (mesmo id) chegar: o consumer não a
    acha no banco, nem pelo id nem pela marca de `message_id` NULL (`sent_echo.adopt_echo`), e a cria. Reenviar não é
    opção (o Contact receberia duas vezes), então o eco é a recuperação.

    Com a gravação feita, o eco do webhook (mesmo id) é descartado pelo dedup, e a UI recebe a saída aqui.

    Sem id da Evolution a Message é gravada com `message_id` NULL, para a resposta do Agent e para o aviso da API
    (`sent_by="system"`, não é o Agent nem um Attendant): o eco depois a reconhece no banco (`sent_echo.adopt_echo`),
    entre processos.

    O envio e a gravação rodam sob o lock `SAVE` do JID, o mesmo que o consumer toma para gravar uma Message do webhook:
    o eco (que pode chegar antes de o envio voltar) espera a Message de saída estar gravada, em qualquer réplica.

    `db` não pode estar em transação aberta com trabalho a perder: a gravação commita tudo o que a Session tiver.
    """
    scope = jid_scope(to.instance_id, to.remote_jid)
    async with conversation_lock(db.get_bind(), SAVE, scope, wait=settings.LOCK_SAVE_WAIT_SECONDS):
        response = await evolution_api.send_text_message(
            instance_name=to.instance_name,
            remote_jid=to.remote_jid,
            text=text,
        )
        sent_id = ((response or {}).get("key") or {}).get("id") or None
        if not sent_id:
            logger.warning("Evolution did not return a message id", sent_by=sent_by)

        timestamp = datetime.now(timezone.utc)
        persist = asyncio.ensure_future(asyncio.to_thread(_persist_reply, db, to, sent_id, text, sent_by, timestamp))
        try:
            # Em thread, e termina antes de publicar: quem lê a Message `from_me` como prova de envio (recuperação do
            # Turn) a encontra commitada antes de a UI receber o evento.
            conversation, contact = await asyncio.shield(persist)
        except asyncio.CancelledError:
            # Turn cancelado (timeout, shutdown) com a thread ainda gravando: a thread não é cancelável. Soltar o lock
            # agora deixaria o eco ler a Message `from_me` sem commit, e o `db.close()` do Turn rodaria com a thread
            # usando a mesma Session. Espera a gravação terminar (curta, limitada pelo banco) e só então propaga.
            error = await settle(persist)
            if error is not None:
                db.rollback()
                logger.error("Failed to persist the outgoing message after cancellation", message_id=sent_id, exc_info=error)
            raise
        except Exception:
            # A saída já saiu; falhar ao gravar não pode reenviar nem derrubar o Turn nem a rota.
            db.rollback()
            logger.exception("Failed to persist the outgoing message, the webhook echo will create it", message_id=sent_id)
            return Sent(sent_id, timestamp, saved=False)
    await publish_message(conversation, contact, sent_id, text, timestamp, True)
    return Sent(sent_id, timestamp, saved=True)
