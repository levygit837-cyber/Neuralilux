import enum

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Index, Numeric, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    instance_id = Column(String, ForeignKey("instances.id"))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    remote_jid = Column(String, nullable=False)  # WhatsApp contact ID
    message_id = Column(String, unique=True, index=True)
    message_type = Column(String, default="text")  # text, image, video, audio, document, location, contact, sticker
    content = Column(Text)
    media_url = Column(String)
    caption = Column(Text)  # Caption for media messages
    latitude = Column(Numeric(10, 8))  # For location messages
    longitude = Column(Numeric(11, 8))  # For location messages
    direction = Column(String, nullable=False)  # incoming, outgoing
    status = Column(String, default="pending")  # pending, sent, delivered, read, failed
    is_from_me = Column(Boolean, default=False)
    sender_name = Column(String(200))  # Quem escreveu, em grupo (pushName do participante); NULL em 1:1
    sent_by = Column(String(20))  # NULL: Contact, Agent ou Attendant; "system": aviso da API (ex.: status do Order, #34)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # History Search (ADR 0003). A expressão tem de ser idêntica à de `memory.search_history` e à da
    # migração 0004; declarada aqui para o autogenerate do Alembic não propor remover o índice.
    __table_args__ = (
        Index(
            "ix_messages_content_fts",
            text("to_tsvector('portuguese', coalesce(content,''))"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )

    # Relationships
    instance = relationship("Instance", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
