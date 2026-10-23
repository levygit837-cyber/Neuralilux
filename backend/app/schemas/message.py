from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from app.schemas.base import PaginationParams


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
    sender_name: Optional[str] = None
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


class MessageFilter(PaginationParams):
    instance_id: Optional[str] = None
    conversation_id: Optional[str] = None
    remote_jid: Optional[str] = None
    direction: Optional[MessageDirectionEnum] = None
    status: Optional[MessageStatusEnum] = None
    message_type: Optional[MessageTypeEnum] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class PaginatedMessages(BaseModel):
    items: List[MessageResponse]
    total: int
    skip: int
    limit: int


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
