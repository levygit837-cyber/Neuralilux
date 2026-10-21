from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum
from app.schemas.base import PaginationParams
from app.schemas.contact import ContactResponse


class PriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ConversationCreate(BaseModel):
    instance_id: str
    contact_id: str
    remote_jid: str
    assigned_agent_id: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: PriorityEnum = PriorityEnum.NORMAL


class ConversationUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None
    assigned_agent_id: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[PriorityEnum] = None


class ConversationResponse(BaseModel):
    id: str
    instance_id: str
    contact_id: str
    remote_jid: str
    is_active: bool
    is_archived: bool
    unread_count: int
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested relationships (optional)
    contact: Optional[ContactResponse] = None

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Lightweight conversation response for list views"""
    id: str
    contact_id: str
    remote_jid: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int
    priority: str
    is_archived: bool

    class Config:
        from_attributes = True


class ConversationFilter(PaginationParams):
    instance_id: Optional[str] = None
    contact_id: Optional[str] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None
    priority: Optional[PriorityEnum] = None
    search: Optional[str] = None  # Search by contact name or phone


class PaginatedConversations(BaseModel):
    items: List[ConversationResponse]
    total: int
    skip: int
    limit: int
