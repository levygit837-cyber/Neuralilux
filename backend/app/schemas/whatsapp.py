from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class InstanceStatusEnum(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MessageDirectionEnum(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MessageStatusEnum(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageTypeEnum(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"


class PriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# ============== WhatsApp Instance Schemas ==============

class WhatsAppInstanceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    owner_id: str


class WhatsAppInstanceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    agent_id: Optional[str] = None
    is_active: Optional[bool] = None


class WhatsAppInstanceResponse(BaseModel):
    id: str
    name: str
    phone_number: Optional[str] = None
    evolution_instance_id: Optional[str] = None
    status: str
    qr_code: Optional[str] = None
    is_active: bool
    owner_id: str
    agent_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InstanceConnectResponse(BaseModel):
    instance_id: str
    status: str
    qr_code: Optional[str] = None
    message: str


class InstanceDisconnectResponse(BaseModel):
    instance_id: str
    status: str
    message: str


# ============== Contact Schemas ==============

class ContactCreate(BaseModel):
    instance_id: str
    phone_number: str = Field(..., min_length=10, max_length=20)
    remote_jid: str
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_blocked: Optional[bool] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    instance_id: str
    phone_number: str
    remote_jid: str
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_blocked: bool
    is_business: bool
    last_seen: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Conversation Schemas ==============

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


# ============== Message Schemas ==============

class MessageCreate(BaseModel):
    instance_id: str
    conversation_id: Optional[str] = None
    remote_jid: str
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    content: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class MessageUpdate(BaseModel):
    status: Optional[MessageStatusEnum] = None
    content: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    remote_jid: str
    message_id: Optional[str] = None
    message_type: str
    content: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    direction: str
    status: str
    is_from_me: bool
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    """Request schema for sending a message via WhatsApp"""
    instance_id: str
    remote_jid: str = Field(..., description="WhatsApp contact JID (e.g., 5511999999999@s.whatsapp.net)")
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    content: Optional[str] = Field(None, description="Text content for text messages")
    media_url: Optional[str] = Field(None, description="URL for media messages")
    caption: Optional[str] = Field(None, description="Caption for media messages")
    latitude: Optional[float] = Field(None, description="Latitude for location messages")
    longitude: Optional[float] = Field(None, description="Longitude for location messages")


class ConversationSendMessageRequest(BaseModel):
    """Request schema for sending a message in a conversation (simpler - conversation provides context)"""
    content: str = Field(..., min_length=1, description="Text content for the message")
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT


class SendMessageResponse(BaseModel):
    """Response schema after sending a message"""
    success: bool
    message_id: Optional[str] = None
    instance_id: str
    remote_jid: str
    status: str
    message: str


# ============== Webhook Schemas ==============

class WebhookMessageKey(BaseModel):
    remoteJid: str
    fromMe: bool
    id: str


class WebhookMessage(BaseModel):
    conversation: Optional[str] = None
    imageMessage: Optional[Dict[str, Any]] = None
    videoMessage: Optional[Dict[str, Any]] = None
    audioMessage: Optional[Dict[str, Any]] = None
    documentMessage: Optional[Dict[str, Any]] = None
    locationMessage: Optional[Dict[str, Any]] = None
    contactMessage: Optional[Dict[str, Any]] = None
    stickerMessage: Optional[Dict[str, Any]] = None


class WebhookMessageData(BaseModel):
    key: WebhookMessageKey
    message: Optional[WebhookMessage] = None
    messageTimestamp: Optional[int] = None
    pushName: Optional[str] = None
    status: Optional[str] = None


class WebhookPayload(BaseModel):
    """Schema for Evolution API webhook payloads"""
    event: str
    instance: str
    data: WebhookMessageData


class ConnectionUpdatePayload(BaseModel):
    """Schema for connection update webhooks"""
    event: str = "connection.update"
    instance: str
    data: Dict[str, Any]


class QrCodeUpdatePayload(BaseModel):
    """Schema for QR code update webhooks"""
    event: str = "qr.updated"
    instance: str
    data: Dict[str, Any]


# ============== Pagination & Filter Schemas ==============

class PaginationParams(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class MessageFilter(PaginationParams):
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    remote_jid: Optional[str] = None
    direction: Optional[MessageDirectionEnum] = None
    status: Optional[MessageStatusEnum] = None
    message_type: Optional[MessageTypeEnum] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class ConversationFilter(PaginationParams):
    instance_id: Optional[str] = None
    contact_id: Optional[str] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None
    priority: Optional[PriorityEnum] = None
    search: Optional[str] = None  # Search by contact name or phone


class ContactFilter(PaginationParams):
    instance_id: Optional[str] = None
    is_blocked: Optional[bool] = None
    is_business: Optional[bool] = None
    search: Optional[str] = None  # Search by name or phone number


# ============== List Response Schemas ==============

class PaginatedMessages(BaseModel):
    items: List[MessageResponse]
    total: int
    skip: int
    limit: int


class PaginatedConversations(BaseModel):
    items: List[ConversationResponse]
    total: int
    skip: int
    limit: int


class PaginatedContacts(BaseModel):
    items: List[ContactResponse]
    total: int
    skip: int
    limit: int


class PaginatedInstances(BaseModel):
    items: List[WhatsAppInstanceResponse]
    total: int
    skip: int
    limit: int