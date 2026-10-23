from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InstanceStatusEnum(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class WhatsAppInstanceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    owner_id: str


class WhatsAppInstanceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    agent_id: Optional[str] = None
    is_active: Optional[bool] = None


class WhatsAppInstanceResponse(BaseModel):
    id: str
    name: str
    phone_number: Optional[str] = None
    evolution_instance_id: Optional[str] = None
    status: str
    qr_code: Optional[str] = None
    is_active: bool
    owner_id: str
    agent_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InstanceConnectResponse(BaseModel):
    instance_id: str
    status: str
    qr_code: Optional[str] = None
    message: str


class InstanceDisconnectResponse(BaseModel):
    instance_id: str
    status: str
    message: str


class PaginatedInstances(BaseModel):
    items: List[WhatsAppInstanceResponse]
    total: int
    skip: int
    limit: int
