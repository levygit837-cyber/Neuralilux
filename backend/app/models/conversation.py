from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.sql import expression
from app.core.database import Base
from app.models.base import generate_uuid


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False)
    remote_jid = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    is_group = Column(Boolean, default=False, server_default=expression.false(), nullable=False)  # chat de grupo (@g.us)
    unread_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True))
    # Início da Session de atendimento atual (ADR 0007). NULL: Conversation anterior às Sessions, janela inteira.
    session_started_at = Column(DateTime(timezone=True))
    # Início da Session anterior à atual, guardado ao virar a Session. NULL: não houve Session anterior (ou é anterior a este campo).
    previous_session_started_at = Column(DateTime(timezone=True))
    last_message_preview = Column(Text)
    assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    human_in_loop = Column(Boolean, default=False, nullable=False)  # True when human took control
    human_handoff_reason = Column(Text, nullable=True)  # Reason for human handoff
    ticket_id = Column(String, ForeignKey("tickets.id", use_alter=True, name="fk_conversations_ticket_id"), nullable=True)  # Reference to ticket
    tags = Column(JSONB)  # Array of tags for categorization
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    rating = Column(Integer, nullable=True)  # Customer satisfaction score (1-5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    instance = relationship("Instance", back_populates="conversations")
    contact = relationship("Contact", back_populates="conversations")
    assigned_agent = relationship("Agent")
    handoff_ticket = relationship("Ticket", foreign_keys=[ticket_id], post_update=True)
    messages = relationship("Message", back_populates="conversation")
    orders = relationship("CustomerOrder", back_populates="conversation")

    @property
    def handoff_assigned_to(self) -> str | None:
        """Attendant (User.id) que assumiu o Handoff em curso; None se ninguém assumiu ou o Agent atende."""
        if not self.human_in_loop or self.handoff_ticket is None:
            return None
        return self.handoff_ticket.assigned_to


class ConversationMemorySummary(Base):
    """Summary acumulado das Messages que já saíram da Recent Window (ADR 0003)."""
    __tablename__ = "conversation_summaries"

    conversation_id = Column(String, ForeignKey("conversations.id"), primary_key=True)
    summary = Column(Text, nullable=False)
    # Última Message coberta pelo Summary; só o que vem depois conta para o próximo refresh.
    covered_until_message_id = Column(String, ForeignKey("messages.id"), nullable=False)
    message_count = Column(Integer, nullable=False)  # Messages cobertas até agora
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
