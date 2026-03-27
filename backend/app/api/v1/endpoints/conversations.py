"""
Conversations & Contacts Endpoints - WhatsApp conversation management.
Integrates with Evolution API service for fetching/sending messages.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User, Instance, Contact, Conversation, Message
from app.schemas.whatsapp import (
    ConversationResponse,
    ConversationSummary,
    ConversationFilter,
    PaginatedConversations,
    ContactResponse,
    ContactFilter,
    PaginatedContacts,
    SendMessageRequest,
    SendMessageResponse,
    MessageResponse,
    PaginatedMessages,
    MessageFilter,
)
from app.services.evolution_api import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


def _get_instance_for_user(
    db: Session,
    instance_id: str,
    current_user: User,
) -> Instance:
    """Helper to fetch and validate instance ownership."""
    instance = db.query(Instance).filter(
        Instance.id == instance_id,
        Instance.is_active == True,
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found",
        )

    if not current_user.is_superuser and instance.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )

    return instance


# =====================================================================
# CONVERSATIONS
# =====================================================================

@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    instance_id: Optional[str] = Query(None, description="Filter by instance ID"),
    contact_id: Optional[str] = Query(None, description="Filter by contact ID"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive conversations"),
    is_archived: Optional[bool] = Query(None, description="Filter archived/unarchived conversations"),
    priority: Optional[str] = Query(None, description="Filter by priority (low, normal, high, urgent)"),
    search: Optional[str] = Query(None, description="Search by contact name or phone"),
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
    if not current_user.is_superuser:
        user_instance_ids = [
            inst.id for inst in db.query(Instance.id).filter(
                Instance.owner_id == current_user.id,
                Instance.is_active == True,
            ).all()
        ]
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
        # Join with Contact to search by name or phone
        query = query.join(Contact).filter(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.phone_number.ilike(f"%{search}%"),
                Contact.push_name.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    conversations = (
        query.order_by(Conversation.last_message_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedConversations(
        items=[ConversationResponse.from_orm(c) for c in conversations],
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
    _get_instance_for_user(db, conversation.instance_id, current_user)

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
        items=[MessageResponse.from_orm(m) for m in messages],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_conversation_message(
    conversation_id: str,
    request: SendMessageRequest,
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
    instance = _get_instance_for_user(db, conversation.instance_id, current_user)

    if instance.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp instance is not connected",
        )

    # Only text messages are supported via this endpoint
    if request.message_type != "text" or not request.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only text messages are supported. Provide 'content' field.",
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
            timestamp=datetime.utcnow(),
        )
        db.add(db_message)

        # Update conversation last message info
        conversation.last_message_at = datetime.utcnow()
        conversation.last_message_preview = request.content[:200] if request.content else None
        db.commit()
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
            detail=f"Evolution API error: {e.message}",
        )


# =====================================================================
# CONTACTS
# =====================================================================

@router.get("/contacts", response_model=PaginatedContacts)
async def list_contacts(
    instance_id: Optional[str] = Query(None, description="Filter by instance ID"),
    is_blocked: Optional[bool] = Query(None, description="Filter blocked contacts"),
    is_business: Optional[bool] = Query(None, description="Filter business contacts"),
    search: Optional[str] = Query(None, description="Search by name or phone number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List contacts with optional filters.

    - **instance_id**: Filter by WhatsApp instance.
    - **is_blocked**: Filter blocked/unblocked contacts.
    - **is_business**: Filter business/regular contacts.
    - **search**: Search by name, push_name or phone number.
    """
    query = db.query(Contact)

    # Filter by instances the user owns (unless superuser)
    if not current_user.is_superuser:
        user_instance_ids = [
            inst.id for inst in db.query(Instance.id).filter(
                Instance.owner_id == current_user.id,
                Instance.is_active == True,
            ).all()
        ]
        query = query.filter(Contact.instance_id.in_(user_instance_ids))

    if instance_id:
        query = query.filter(Contact.instance_id == instance_id)

    if is_blocked is not None:
        query = query.filter(Contact.is_blocked == is_blocked)

    if is_business is not None:
        query = query.filter(Contact.is_business == is_business)

    if search:
        query = query.filter(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.phone_number.ilike(f"%{search}%"),
                Contact.push_name.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    contacts = (
        query.order_by(Contact.name.asc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedContacts(
        items=[ContactResponse.from_orm(c) for c in contacts],
        total=total,
        skip=skip,
        limit=limit,
    )
