from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, Numeric, Enum, UniqueConstraint
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
    menu_catalogs = relationship("MenuCatalog", back_populates="company")


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
    agent_enabled = Column(Boolean, default=True)  # Toggle para habilitar/desabilitar agente
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="instances")
    agent = relationship("Agent", back_populates="instances")
    messages = relationship("Message", back_populates="instance")
    contacts = relationship("Contact", back_populates="instance")
    conversations = relationship("Conversation", back_populates="instance")
    orders = relationship("CustomerOrder", back_populates="instance")


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
    orders = relationship("CustomerOrder", back_populates="contact")


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
    orders = relationship("CustomerOrder", back_populates="conversation")


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


class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    id = Column(String, primary_key=True, default=generate_uuid)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False, index=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False, index=True)
    remote_jid = Column(String, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="open")  # open, collecting_data, ready_for_confirmation, closed, cancelled
    customer_name = Column(String(200))
    customer_address = Column(Text)
    customer_phone = Column(String(30))
    payment_method = Column(String(100))
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    export_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversation = relationship("Conversation", back_populates="orders")
    instance = relationship("Instance", back_populates="orders")
    contact = relationship("Contact", back_populates="orders")
    items = relationship(
        "CustomerOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="CustomerOrderItem.sort_order.asc()",
    )


class CustomerOrderItem(Base):
    __tablename__ = "customer_order_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    order_id = Column(String, ForeignKey("customer_orders.id"), nullable=False, index=True)
    menu_item_id = Column(String, ForeignKey("menu_items.id"), nullable=True, index=True)
    item_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0)
    subtotal_price = Column(Numeric(10, 2), nullable=False, default=0)
    notes = Column(Text)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("CustomerOrder", back_populates="items")


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


class MenuCatalog(Base):
    __tablename__ = "menu_catalogs"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), default="json")
    source_file = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_menu_catalog_company_name"),
    )

    company = relationship("Company", back_populates="menu_catalogs")
    categories = relationship("MenuCategory", back_populates="catalog", cascade="all, delete-orphan")
    items = relationship("MenuItem", back_populates="catalog", cascade="all, delete-orphan")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(String, primary_key=True, default=generate_uuid)
    catalog_id = Column(String, ForeignKey("menu_catalogs.id"), nullable=False, index=True)
    external_id = Column(String(100), index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    raw_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("catalog_id", "external_id", name="uq_menu_category_catalog_external"),
    )

    catalog = relationship("MenuCatalog", back_populates="categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    catalog_id = Column(String, ForeignKey("menu_catalogs.id"), nullable=False, index=True)
    category_id = Column(String, ForeignKey("menu_categories.id"), nullable=False, index=True)
    external_id = Column(String(100), index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2))
    image_url = Column(String(500))
    is_available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    custom_attributes = Column(JSONB, default=list, nullable=False)
    raw_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("catalog_id", "external_id", name="uq_menu_item_catalog_external"),
    )

    catalog = relationship("MenuCatalog", back_populates="items")
    category = relationship("MenuCategory", back_populates="items")


# ============== Super Agent Models ==============


class SuperAgentSession(Base):
    """Session management for the Super Agent (Business Assistant)."""
    __tablename__ = "super_agent_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200))
    is_active = Column(Boolean, default=True)
    interaction_count = Column(Integer, default=0)
    last_checkpoint_at = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    user = relationship("User")
    messages = relationship("SuperAgentMessage", back_populates="session", order_by="SuperAgentMessage.created_at")
    checkpoints = relationship("SuperAgentCheckpoint", back_populates="session")


class SuperAgentMessage(Base):
    """Messages within a Super Agent session."""
    __tablename__ = "super_agent_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("super_agent_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text)
    tool_name = Column(String(100))
    tool_input = Column(JSONB)
    tool_output = Column(Text)
    thinking_content = Column(Text)
    extra_data = Column(JSONB)  # Renamed from 'metadata' (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("SuperAgentSession", back_populates="messages")


class SuperAgentCheckpoint(Base):
    """Checkpoints every 5 interactions for session recovery."""
    __tablename__ = "super_agent_checkpoints"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("super_agent_sessions.id"), nullable=False, index=True)
    interaction_number = Column(Integer, nullable=False)
    summary = Column(Text)
    context_snapshot = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("SuperAgentSession", back_populates="checkpoints")

    __table_args__ = (
        UniqueConstraint("session_id", "interaction_number", name="uq_checkpoint_session_number"),
    )


class SuperAgentKnowledge(Base):
    """Cross-session knowledge base for the Super Agent."""
    __tablename__ = "super_agent_knowledge"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    source_session_id = Column(String, ForeignKey("super_agent_sessions.id"), nullable=True)
    confidence = Column(Integer, default=100)
    access_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    source_session = relationship("SuperAgentSession")

    __table_args__ = (
        UniqueConstraint("company_id", "category", "key", name="uq_knowledge_company_category_key"),
    )


class SuperAgentDocument(Base):
    """Documents created by the Super Agent."""
    __tablename__ = "super_agent_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("super_agent_sessions.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # "pdf", "txt", "json", "markdown"
    content = Column(Text)
    content_base64 = Column(Text)
    file_size = Column(Integer)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("SuperAgentSession")
    company = relationship("Company")
