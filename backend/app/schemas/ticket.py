"""Schemas de leitura de Ticket. Assumir e devolver passam pelas rotas de controle humano da Conversation."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    instance_id: str
    contact_id: str
    agent_type: str
    reason: str
    content: str
    status: str
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse]
    total: int
    skip: int
    limit: int
