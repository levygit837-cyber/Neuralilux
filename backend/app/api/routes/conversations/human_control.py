"""Handoff - o Attendant assume, devolve e consulta o controle da Conversation.

Assumir liga o Handoff (abrindo um Ticket se não havia) e atribui o Ticket ao Attendant; outro Attendant
já com a Conversation recebe 409 e o mesmo Attendant, 200. Devolver ao Agent fecha o Ticket. Quem de fato
muda o estado avisa a UI por `handoff_updated`. A consulta de status só lê.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.access import get_instance_for_user
from app.api.deps import get_current_user, get_db
from app.models import Company, Conversation, Instance, Ticket, User
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
    # Só leitura: o Handoff já passou do timeout da Company e o worker vai devolvê-lo ao Agent.
    timeout_due: bool = False
    message: str


def _load(db: Session, conversation_id: str, user: User) -> tuple[Conversation, Instance]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    instance = get_instance_for_user(db, conversation.instance_id, user)
    return conversation, instance


def _response(
    conversation: Conversation, ticket: Optional[Ticket], message: str, *, timeout_due: bool = False
) -> HumanControlResponse:
    return HumanControlResponse(
        conversation_id=conversation.id,
        human_in_loop=bool(conversation.human_in_loop),
        human_handoff_reason=conversation.human_handoff_reason,
        ticket_id=conversation.ticket_id,
        assigned_to=ticket.assigned_to if ticket and conversation.human_in_loop else None,
        ticket_status=ticket.status if ticket else None,
        timeout_due=timeout_due,
        message=message,
    )


def _take(db: Session, conversation_id: str, user: User, reason: Optional[str]):
    """Assume a Conversation (bloqueante: roda em thread). Devolve os objetos já recarregados: o `announce` roda no
    event loop e lê só atributos, então nada pode estar expirado (o commit de `assume` expira tudo)."""
    conversation, instance = _load(db, conversation_id, user)
    try:
        ticket = handoff_service.assume(db, conversation, user, reason)
    except handoff_service.HeldByAnotherAttendant:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Outro atendente já assumiu esta conversa")
    db.refresh(conversation)
    db.refresh(instance)
    db.refresh(ticket)
    return conversation, instance, ticket


def _release(db: Session, conversation_id: str, user: User):
    """Devolve a Conversation ao Agent (bloqueante: roda em thread); mesmo contrato de objetos recarregados."""
    conversation, instance = _load(db, conversation_id, user)
    released = handoff_service.release(db, conversation)
    db.refresh(conversation)
    if released is not None:
        db.refresh(instance)
        db.refresh(released.ticket)
    return conversation, instance, released


@router.post("/conversations/{conversation_id}/take-control", response_model=HumanControlResponse)
async def take_conversation_control(
    conversation_id: str,
    request: HumanControlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """O Attendant assume a Conversation: o Agent para de responder até o Attendant devolver ou o timeout vencer."""
    user_id = current_user.id  # lido antes: o commit do Handoff expira o usuário e a leitura iria ao banco, no loop
    conversation, instance, ticket = await run_in_threadpool(_take, db, conversation_id, current_user, request.reason)
    await handoff_service.announce(instance, conversation, "assumed", ticket)
    logger.info("Attendant took control", conversation_id=conversation.id, user_id=user_id, ticket_id=ticket.id)
    return _response(conversation, ticket, "Atendimento assumido. O Agent está pausado nesta conversa.")


@router.post("/conversations/{conversation_id}/release-control", response_model=HumanControlResponse)
async def release_conversation_control(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devolve a Conversation ao Agent e fecha o Ticket. Sem Handoff em curso, não muda nada."""
    user_id = current_user.id  # lido antes: o commit do Handoff expira o usuário e a leitura iria ao banco, no loop
    conversation, instance, released = await run_in_threadpool(_release, db, conversation_id, current_user)
    if released is None:  # já estava com o Agent, ou o timeout devolveu antes: nada mudou, nada a anunciar
        return _response(conversation, None, "A conversa já está com o Agent.")
    await handoff_service.announce(instance, conversation, "released", released.ticket)
    logger.info("Attendant released control", conversation_id=conversation.id, user_id=user_id)
    return _response(
        conversation, released.ticket, "Conversa devolvida ao Agent. Ele volta a responder na próxima mensagem."
    )


@router.get("/conversations/{conversation_id}/human-control-status", response_model=HumanControlResponse)
def get_human_control_status(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estado atual do Handoff, somente leitura. `timeout_due` avisa que o prazo venceu e o worker vai devolvê-lo."""
    conversation, instance = _load(db, conversation_id, current_user)
    ticket = db.get(Ticket, conversation.ticket_id) if conversation.ticket_id else None
    company = db.get(Company, instance.company_id) if instance.company_id else None
    due = handoff_service.is_overdue(db, conversation, company)
    message = (
        "A conversa está com um atendente. O Agent está pausado."
        if conversation.human_in_loop
        else "A conversa está com o Agent."
    )
    return _response(conversation, ticket, message, timeout_due=due)
