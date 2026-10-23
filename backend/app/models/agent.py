from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(Text)
    system_prompt = Column(Text, nullable=True)  # instruções da Company (painel); vazio = sem trecho no system
    company_id = Column(String, ForeignKey("companies.id"), nullable=True, index=True)  # um Agent por Company
    model = Column(String, nullable=True)  # o modelo vem do Gateway; só sobrescreve se preenchido
    temperature = Column(Float, nullable=True)  # None: usa a do Gateway
    max_tokens = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="agents")
    company = relationship("Company", back_populates="agents")
    instances = relationship("Instance", back_populates="agent")
