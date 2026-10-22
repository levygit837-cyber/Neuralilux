"""Handoff - o Attendant assume, devolve e consulta o controle da Conversation.

Assumir liga o Handoff (abrindo um Ticket se não havia) e atribui o Ticket ao Attendant. Devolver ao Agent
fecha o Ticket. Os dois avisam a UI por `handoff_updated`.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.access import get_instance_for_user
from app.api.deps import get_current_user, get_db
from app.models import Conversation, Instance, Ticket, User
from app.services import handoff_service

logger = structlog.get_logger()

router = APIRouter()


class HumanControlRequest(BaseModel):
    reason: Optional[str] = None


class HumanControlResponse(BaseModel):
    conversation_id: str
    human_in_loop: bool
    human_handoff_reason: Optional[str]
    ticket_id: Optional[str]
    assigned_to: Optional[str] = None
    ticket_status: Optional[str] = None
    message: str


def _load(db: Session, conversation_id: str, user: User) -> tuple[Conversation, Instance]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    instance = get_instance_for_user(db, conversation.instance_id, user)
    return conversation, instance


def _response(conversation: Conversation, ticket: Optional[Ticket], message: str) -> HumanControlResponse:
    return HumanControlResponse(
        conversation_id=conversation.id,
        human_in_loop=bool(conversation.human_in_loop),
        human_handoff_reason=conversation.human_handoff_reason,
        ticket_id=conversation.ticket_id,
        assigned_to=ticket.assigned_to if ticket and conversation.human_in_loop else None,
        ticket_status=ticket.status if ticket else None,
        message=message,
    )


@router.post("/conversations/{conversation_id}/take-control", response_model=HumanControlResponse)
async def take_conversation_control(
    conversation_id: str,
    request: HumanControlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """O Attendant assume a Conversation: o Agent para de responder até o Attendant devolver ou o timeout vencer."""
    conversation, instance = _load(db, conversation_id, current_user)
    ticket = handoff_service.assume(db, conversation, current_user, request.reason)
    await handoff_service.announce(instance, conversation, "assumed", ticket)
    logger.info("Attendant took control", conversation_id=conversation.id, user_id=current_user.id, ticket_id=ticket.id)
    return _response(conversation, ticket, "Atendimento assumido. O Agent está pausado nesta conversa.")


@router.post("/conversations/{conversation_id}/release-control", response_model=HumanControlResponse)
async def release_conversation_control(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devolve a Conversation ao Agent e fecha o Ticket. Sem Handoff em curso, não muda nada."""
    conversation, instance = _load(db, conversation_id, current_user)
    if not conversation.human_in_loop:
        return _response(conversation, None, "A conversa já está com o Agent.")
    ticket = handoff_service.release(db, conversation)
    await handoff_service.announce(instance, conversation, "released", ticket)
    logger.info("Attendant released control", conversation_id=conversation.id, user_id=current_user.id)
    return _response(conversation, ticket, "Conversa devolvida ao Agent. Ele volta a responder na próxima mensagem.")


@router.get("/conversations/{conversation_id}/human-control-status", response_model=HumanControlResponse)
async def get_human_control_status(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estado atual do Handoff. Um Handoff vencido é devolvido ao Agent antes de responder."""
    conversation, instance = _load(db, conversation_id, current_user)
    if await handoff_service.expire_if_due(db, conversation, instance):
        return _response(conversation, None, "O tempo sem atendente venceu; a conversa voltou ao Agent.")
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.ticket_id else None
    message = (
        "A conversa está com um atendente. O Agent está pausado."
        if conversation.human_in_loop
        else "A conversa está com o Agent."
    )
    return _response(conversation, ticket, message)
