from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False)
    phone_number = Column(String(20), nullable=False, index=True)
    remote_jid = Column(String, nullable=False, index=True)  # WhatsApp JID format
    name = Column(String(200))
    push_name = Column(String(200))  # Name set by contact on WhatsApp
    profile_pic_url = Column(String(500))
    is_blocked = Column(Boolean, default=False)
    is_business = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # `get_or_create_contact` se apoia nesta unicidade (INSERT ... ON CONFLICT DO NOTHING). Cobre também o filtro
    # por `instance_id` sozinho (dashboard, busca): o prefixo do índice.
    __table_args__ = (UniqueConstraint("instance_id", "remote_jid", name="uq_contacts_instance_remote_jid"),)

    # Relationships
    instance = relationship("Instance", back_populates="contacts")
    conversations = relationship("Conversation", back_populates="contact")
    orders = relationship("CustomerOrder", back_populates="contact")
