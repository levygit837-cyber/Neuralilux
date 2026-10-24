from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


# Limite padrão de inatividade da Session de atendimento (ADR 0007), em minutos.
DEFAULT_SESSION_TIMEOUT_MINUTES = 180


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
    pix_key = Column(String(500))  # Chave Pix para pagamentos
    business_hours = Column(JSONB)  # {"mon": [["11:00", "23:00"]], ...}; intervalo que cruza a meia-noite é aceito
    timezone = Column(String(64), nullable=False, default="America/Sao_Paulo", server_default="America/Sao_Paulo")
    minimum_order = Column(Numeric(10, 2))  # Pedido mínimo (soma dos itens) da Company
    # Minutos sem Messages que encerram a Session de atendimento (ADR 0007).
    session_timeout_minutes = Column(
        Integer,
        nullable=False,
        default=DEFAULT_SESSION_TIMEOUT_MINUTES,
        server_default=str(DEFAULT_SESSION_TIMEOUT_MINUTES),
    )
    # Horas sem Attendant agir até a Conversation voltar sozinha ao Agent (Ticket vira `expired`).
    handoff_timeout_hours = Column(Integer, nullable=False, default=4, server_default="4")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    business_type = relationship("BusinessType", back_populates="companies")
    users = relationship("User", back_populates="company")
    instances = relationship("Instance", back_populates="company")
    agents = relationship("Agent", back_populates="company")
    menu_catalogs = relationship("MenuCatalog", back_populates="company")
