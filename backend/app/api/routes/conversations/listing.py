"""
Conversations - mensagens de uma Conversation (lista, histórico e envio).
Usa o cliente da Evolution API para buscar e enviar Messages.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import structlog

from app.api.access import get_instance_for_user, instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.api.routes.conversations.categories import Category, apply_category, apply_search
from app.models import User, Conversation, Message
from app.services import handoff_service
from app.schemas.conversation import ConversationResponse, PaginatedConversations
from app.schemas.message import (
    ConversationSendMessageRequest,
    MessageResponse,
    PaginatedMessages,
    SendMessageResponse,
)
from app.whatsapp.evolution_client import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    instance_id: Optional[str] = Query(None, description="Filter by instance ID"),
    contact_id: Optional[str] = Query(None, description="Filter by contact ID"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive conversations"),
    is_archived: Optional[bool] = Query(None, description="Filter archived/unarchived conversations"),
    priority: Optional[str] = Query(None, description="Filter by priority (low, normal, high, urgent)"),
    search: Optional[str] = Query(None, description="Search by contact name, phone or last message"),
    category: Category = Query("all", description="all, unread, groups, ai ou human"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List conversations with optional filters.

    - **instance_id**: Filter by WhatsApp instance.
    - **contact_id**: Filter by specific contact.
    - **is_active**: Filter active/inactive conversations.
    - **is_archived**: Filter archived/unarchived.
    - **priority**: Filter by priority level.
    - **search**: Search by contact name or phone number.
    """
    query = db.query(Conversation)

    # Filter by instances the user owns (unless superuser)
    user_instance_ids = instance_ids_for_user(db, current_user)
    if user_instance_ids is not None:
        query = query.filter(Conversation.instance_id.in_(user_instance_ids))

    if instance_id:
        query = query.filter(Conversation.instance_id == instance_id)

    if contact_id:
        query = query.filter(Conversation.contact_id == contact_id)

    if is_active is not None:
        query = query.filter(Conversation.is_active == is_active)

    if is_archived is not None:
        query = query.filter(Conversation.is_archived == is_archived)

    if priority:
        query = query.filter(Conversation.priority == priority)

    if search:
        query = apply_search(query, search)
    query = apply_category(query, category)

    total = query.count()
    conversations = (
        query.order_by(Conversation.last_message_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedConversations(
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessages)
async def get_conversation_messages(
    conversation_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get message history for a specific conversation.

    - **conversation_id**: The ID of the conversation.
    - **skip**: Number of messages to skip (pagination).
    - **limit**: Maximum number of messages to return.
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Validate ownership through instance
    get_instance_for_user(db, conversation.instance_id, current_user)

    query = db.query(Message).filter(
        Message.conversation_id == conversation_id,
    )

    total = query.count()
    messages = (
        query.order_by(Message.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedMessages(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_conversation_message(
    conversation_id: str,
    request: ConversationSendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message in a specific conversation via WhatsApp.

    - **conversation_id**: The ID of the conversation.
    - **request**: Message details including content and type.
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Validate ownership through instance
    instance = get_instance_for_user(db, conversation.instance_id, current_user)

    if instance.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp instance is not connected",
        )

    # Only text messages are supported via this endpoint
    if request.message_type != "text":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only text messages are supported.",
        )

    try:
        # Send message via Evolution API
        result = await evolution_api.send_text_message(
            instance_name=instance.evolution_instance_id,
            remote_jid=conversation.remote_jid,
            text=request.content,
        )

        # Extract message ID from Evolution API response
        evolution_message_id = None
        if isinstance(result, dict):
            evolution_message_id = (
                result.get("key", {}).get("id")
                or result.get("message", {}).get("id")
                or result.get("id")
            )

        # Save message to database
        db_message = Message(
            instance_id=instance.id,
            conversation_id=conversation.id,
            remote_jid=conversation.remote_jid,
            message_id=evolution_message_id,
            message_type="text",
            content=request.content,
            direction="outgoing",
            status="sent",
            is_from_me=True,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(db_message)

        # Update conversation last message info
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.last_message_preview = request.content[:200] if request.content else None
        db.commit()
        # Um Attendant escreveu pelo painel: reinicia o timeout do Handoff.
        handoff_service.record_attendant_activity(db, conversation)
        db.refresh(db_message)

        logger.info(
            "Message sent successfully",
            conversation_id=conversation_id,
            message_id=evolution_message_id,
            instance_id=instance.id,
        )

        return SendMessageResponse(
            success=True,
            message_id=evolution_message_id,
            instance_id=instance.id,
            remote_jid=conversation.remote_jid,
            status="sent",
            message="Message sent successfully",
        )

    except EvolutionAPIError as e:
        logger.error(
            "Failed to send message",
            conversation_id=conversation_id,
            error=e.message,
        )
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
