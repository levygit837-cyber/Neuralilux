"""Estado da lista de chats: contadores por categoria, leitura de uma Conversation e sincronização do histórico."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import structlog

from app.api.access import get_instance_for_user
from app.api.deps import get_current_user, get_db
from app.api.routes.conversations.categories import category_counts
from app.models import Conversation, Instance, User
from app.whatsapp import history_sync
from app.whatsapp.evolution_client import EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/conversations/counts")
def conversation_counts(
    instance_id: str = Query(..., description="Instance cujas Conversations são contadas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Contadores das abas da lista (arquivadas fora) e total de mensagens não lidas."""
    instance = get_instance_for_user(db, instance_id, current_user)
    return category_counts(db, instance.id)


def _authorize_sync(db: Session, instance_id: str, user: User) -> Instance:
    """Autoriza a importação (bloqueante: roda em thread). A Instance volta com os atributos carregados, que o
    `sync_instance` lê no event loop antes do primeiro commit."""
    instance = get_instance_for_user(db, instance_id, user)
    if instance.status != "connected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp instance is not connected")
    return instance


@router.post("/conversations/sync")
async def sync_conversations(
    instance_id: str = Query(..., description="Instance cujo histórico será importado da Evolution"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Importa o histórico da Evolution (chats, grupos e Messages) e devolve quantas linhas foram criadas."""
    instance = await run_in_threadpool(_authorize_sync, db, instance_id, current_user)
    local_id = instance.id  # lido antes da importação: os commits dela expiram a Instance
    try:
        return await history_sync.sync_instance(db, instance)
    except history_sync.SyncAlreadyRunning:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sincronização já em andamento")
    except EvolutionAPIError as error:
        await run_in_threadpool(db.rollback)
        logger.error("History sync failed", instance_id=local_id, error=error.message)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Evolution API error")
    except IntegrityError:
        # O worker gravou as mesmas Messages durante a importação e as tentativas do lote se esgotaram.
        await run_in_threadpool(db.rollback)
        logger.warning("History sync lost a race with the worker", instance_id=local_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="History sync conflicted with live messages; try again"
        )


@router.post("/conversations/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Zera as não lidas da Conversation."""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    get_instance_for_user(db, conversation.instance_id, current_user)
    conversation.unread_count = 0
    db.commit()
    return {"unread_count": 0}
