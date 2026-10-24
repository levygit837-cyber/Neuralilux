from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.schemas.contact import ContactResponse


class ConversationResponse(BaseModel):
    id: str
    instance_id: str
    contact_id: str
    remote_jid: str
    is_active: bool
    is_archived: bool
    is_group: bool = False
    unread_count: int
    human_in_loop: bool = False
    handoff_assigned_to: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested relationships (optional)
    contact: Optional[ContactResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedConversations(BaseModel):
    items: List[ConversationResponse]
    total: int
    skip: int
    limit: int
