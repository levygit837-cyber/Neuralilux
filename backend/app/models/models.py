from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    instances = relationship("Instance", back_populates="owner")
    agents = relationship("Agent", back_populates="owner")


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
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="instances")
    agent = relationship("Agent", back_populates="instances")
    messages = relationship("Message", back_populates="instance")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    model = Column(String, default="gpt-4-turbo-preview")
    temperature = Column(Integer, default=70)  # 0-100
    max_tokens = Column(Integer, default=1000)
    use_rag = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="agents")
    instances = relationship("Instance", back_populates="agent")
    documents = relationship("Document", back_populates="agent")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    instance_id = Column(String, ForeignKey("instances.id"))
    remote_jid = Column(String, nullable=False)  # WhatsApp contact ID
    message_id = Column(String, unique=True, index=True)
    content = Column(Text)
    media_url = Column(String)
    direction = Column(String, nullable=False)  # incoming, outgoing
    status = Column(String, default="pending")  # pending, sent, delivered, read, failed
    is_from_me = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    instance = relationship("Instance", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    agent_id = Column(String, ForeignKey("agents.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)
    is_processed = Column(Boolean, default=False)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("Agent", back_populates="documents")
