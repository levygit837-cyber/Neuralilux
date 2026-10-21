from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class Ticket(Base):
    """Tickets para chamar atendentes humanos no atendimento WhatsApp."""
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False, index=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False, index=True)
    agent_type = Column(String(20), nullable=False)  # "sales" ou "sac"
    reason = Column(Text, nullable=False)  # Motivo do ticket
    content = Column(Text, nullable=False)  # Conteúdo da reclamação/mensagem do usuário
    status = Column(String(20), nullable=False, default="open")  # "open", "in_progress", "closed"
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)  # ID do atendente humano
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
    instance = relationship("Instance", foreign_keys=[instance_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_user = relationship("User", foreign_keys=[assigned_to])
