"""Handoff - o Attendant assume, devolve e consulta o controle da Conversation."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import structlog

from app.api.deps import get_current_user, get_db
from app.api.access import get_instance_for_user
from app.models import User, Conversation

logger = structlog.get_logger()

router = APIRouter()


class HumanControlRequest(BaseModel):
    reason: Optional[str] = None


class HumanControlResponse(BaseModel):
    conversation_id: str
    human_in_loop: bool
    human_handoff_reason: Optional[str]
    ticket_id: Optional[str]
    message: str


@router.post("/conversations/{conversation_id}/take-control", response_model=HumanControlResponse)
async def take_conversation_control(
    conversation_id: str,
    request: HumanControlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Human takes control of a conversation, pausing the AI agent.

    The agent will stop responding to messages until control is released.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Verify user has access to this conversation's instance
    get_instance_for_user(db, conversation.instance_id, current_user)

    # Update conversation state
    conversation.human_in_loop = True
    conversation.human_handoff_reason = request.reason or "Manual takeover by human"
    conversation.assigned_agent_id = current_user.id
    db.commit()

    logger.info(
        "Human took control of conversation",
        conversation_id=conversation_id,
        user_id=current_user.id,
        reason=request.reason
    )

    return HumanControlResponse(
        conversation_id=conversation_id,
        human_in_loop=True,
        human_handoff_reason=conversation.human_handoff_reason,
        ticket_id=conversation.ticket_id,
        message="Human has taken control of this conversation. AI agent is paused."
    )


@router.post("/conversations/{conversation_id}/release-control", response_model=HumanControlResponse)
async def release_conversation_control(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Human releases control back to the AI agent.

    The agent will resume responding to messages.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Verify user has access to this conversation's instance
    get_instance_for_user(db, conversation.instance_id, current_user)

    # Update conversation state
    conversation.human_in_loop = False
    conversation.human_handoff_reason = None
    conversation.assigned_agent_id = None
    db.commit()

    logger.info(
        "Human released control of conversation",
        conversation_id=conversation_id,
        user_id=current_user.id
    )

    return HumanControlResponse(
        conversation_id=conversation_id,
        human_in_loop=False,
        human_handoff_reason=None,
        ticket_id=conversation.ticket_id,
        message="Control released. AI agent will resume responding to messages."
    )


@router.get("/conversations/{conversation_id}/human-control-status", response_model=HumanControlResponse)
async def get_human_control_status(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current human-in-the-loop status of a conversation.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Verify user has access to this conversation's instance
    get_instance_for_user(db, conversation.instance_id, current_user)

    message = (
        "Conversation is currently under human control. AI agent is paused."
        if conversation.human_in_loop
        else "Conversation is under AI agent control."
    )

    return HumanControlResponse(
        conversation_id=conversation_id,
        human_in_loop=conversation.human_in_loop,
        human_handoff_reason=conversation.human_handoff_reason,
        ticket_id=conversation.ticket_id,
        message=message
    )
