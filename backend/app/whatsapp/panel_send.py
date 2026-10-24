"""Envio de um Attendant pelo painel (HTTP e Socket.IO): o mesmo `send_and_persist` do worker, mais o relógio do Handoff."""
import structlog
from sqlalchemy.orm import Session

from app.core.threads import in_thread
from app.models import Conversation
from app.services import handoff_service
from app.whatsapp.sender import Recipient, Sent, send_and_persist

logger = structlog.get_logger()


def _record_attendant_activity(db: Session, conversation_id: str) -> None:
    """Bloqueante: roda em thread. O Attendant escreveu pelo painel: reinicia o timeout do Handoff. Falha só loga, pois a
    Message já saiu e não há o que desfazer."""
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None:
            handoff_service.record_attendant_activity(db, conversation)
    except Exception:
        db.rollback()
        logger.exception("Failed to record attendant activity", conversation_id=conversation_id)


async def send_from_panel(db: Session, to: Recipient, text: str) -> Sent:
    """Envia, grava a Message (sem `sent_by`: é um Attendant) e reinicia o timeout do Handoff.

    Levanta se o envio falha (`EvolutionAPIError`) ou se o lock do JID não vem (`LockBusy`): nada saiu. Depois de o envio
    sair nada levanta mais: falha ao gravar vira `Sent(saved=False)` e o eco do webhook cria a Message.
    """
    sent = await send_and_persist(db, to, text)
    await in_thread(_record_attendant_activity, db, to.conversation_id)
    return sent
