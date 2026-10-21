from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class InferenceGateway(Base):
    """Gateway OpenAI-compatible (`/chat/completions`) cadastrado pelo usuario."""
    __tablename__ = "inference_gateways"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, unique=True)
    base_url = Column(String(500), nullable=False)  # raiz da API, ex.: http://host:5580/v1
    api_key_encrypted = Column(Text, nullable=True)  # Fernet; NUNCA devolver pela API
    timeout_seconds = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    models = relationship(
        "GatewayModel",
        back_populates="gateway",
        cascade="all, delete-orphan",
        order_by="GatewayModel.created_at",
    )


class GatewayModel(Base):
    """Modelo nomeado dentro de um gateway, com parametros proprios."""
    __tablename__ = "gateway_models"
    __table_args__ = (UniqueConstraint("gateway_id", "name", name="uq_gateway_models_gateway_name"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    gateway_id = Column(
        String, ForeignKey("inference_gateways.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)  # apelido exibido na UI
    model_id = Column(String(200), nullable=False)  # identificador enviado ao gateway
    reasoning_effort = Column(String(20), nullable=True)  # low | medium | high
    max_tokens = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    supports_tools = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    gateway = relationship("InferenceGateway", back_populates="models")


class GatewayAssignment(Base):
    """Qual modelo de gateway atende cada tipo de agente (default | whatsapp_agent)."""
    __tablename__ = "gateway_assignments"

    agent_type = Column(String(50), primary_key=True)
    gateway_model_id = Column(
        String, ForeignKey("gateway_models.id", ondelete="CASCADE"), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    gateway_model = relationship("GatewayModel")
