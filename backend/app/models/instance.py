import enum

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class InstanceStatus(str, enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class Instance(Base):
    __tablename__ = "instances"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True)
    evolution_instance_id = Column(String, unique=True, index=True)
    status = Column(String, default="disconnected")  # disconnected, connecting, connected
    qr_code = Column(Text)
    is_active = Column(Boolean, default=True)
    owner_id = Column(String, ForeignKey("users.id"))
    company_id = Column(String, ForeignKey("companies.id"))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    agent_enabled = Column(Boolean, default=True)  # Toggle para habilitar/desabilitar agente
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="instances")
    company = relationship("Company", back_populates="instances")
    agent = relationship("Agent", back_populates="instances")
    messages = relationship("Message", back_populates="instance")
    contacts = relationship("Contact", back_populates="instance")
    conversations = relationship("Conversation", back_populates="instance")
    orders = relationship("CustomerOrder", back_populates="instance")
