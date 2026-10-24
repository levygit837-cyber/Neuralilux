from typing import Any, Optional

from pydantic import BaseModel, Field
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


class InstanceListItem(BaseModel):
    id: str
    instance_id: str
    name: str
    status: str
    owner: str | None
    owner_id: str | None
    company_id: str | None
    agent_id: str | None
    agent_enabled: bool
    profile_name: str | None
    profile_pic_url: str | None
    server_url: str | None


class InstanceList(BaseModel):
    instances: list[InstanceListItem]
    total: int


class InstanceStatusResponse(BaseModel):
    instance_id: str
    status: str
    evolution_state: str
    raw: Any


class InstanceConnectResponse(BaseModel):
    instance_id: str
    qr_code: str | None
    status: str
    message: str


class InstanceCreateResponse(BaseModel):
    instance_id: str
    id: str
    status: str
    qr_code: str | None
    message: str


class InstanceDisconnectResponse(BaseModel):
    """Logout e exclusão têm a mesma forma."""

    instance_id: str
    status: str
    message: str
    raw: Any


class AgentState(BaseModel):
    instance_id: str
    instance_name: str
    agent_enabled: bool
    agent_id: str | None
    agent_name: str | None


class AgentStateChange(AgentState):
    message: str
