from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import enum


def generate_uuid():
    return str(uuid.uuid4())


class InstanceStatus(str, enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


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


class BusinessType(Base):
    __tablename__ = "business_types"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    companies = relationship("Company", back_populates="business_type")


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    business_type_id = Column(String, ForeignKey("business_types.id"))
    description = Column(Text)
    logo_url = Column(String(500))

    # Address
    address_street = Column(String(200))
    address_number = Column(String(20))
    address_complement = Column(String(100))
    address_neighborhood = Column(String(100))
    address_city = Column(String(100))
    address_state = Column(String(2))
    address_zip = Column(String(10))

    # Contacts
    phone = Column(String(20))
    email = Column(String(100))
    whatsapp = Column(String(20))
    website = Column(String(200))

    # Business hours (JSON)
    business_hours = Column(JSONB)

    # AI Configuration
    ai_system_prompt = Column(Text)
    ai_model = Column(String(50), default="gpt-4-turbo-preview")
    ai_temperature = Column(Integer, default=70)
    ai_max_tokens = Column(Integer, default=1000)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    business_type = relationship("BusinessType", back_populates="companies")
    users = relationship("User", back_populates="company")
    products = relationship("Product", back_populates="company")


class ProductType(Base):
    __tablename__ = "product_types"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    products = relationship("Product", back_populates="product_type")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    company_id = Column(String, ForeignKey("companies.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="users")
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
    contacts = relationship("Contact", back_populates="instance")
    conversations = relationship("Conversation", back_populates="instance")


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

    # Relationships
    instance = relationship("Instance", back_populates="contacts")
    conversations = relationship("Conversation", back_populates="contact")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False)
    remote_jid = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    unread_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True))
    last_message_preview = Column(Text)
    assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    tags = Column(JSONB)  # Array of tags for categorization
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    instance = relationship("Instance", back_populates="conversations")
    contact = relationship("Contact", back_populates="conversations")
    assigned_agent = relationship("Agent")
    messages = relationship("Message", back_populates="conversation")


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
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    instance = relationship("Instance", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")


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


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    product_type_id = Column(String, ForeignKey("product_types.id"))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    image_url = Column(String(500))
    sku = Column(String(50), unique=True, index=True)
    is_available = Column(Boolean, default=True)
    stock_quantity = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="products")
    product_type = relationship("ProductType", back_populates="products")
