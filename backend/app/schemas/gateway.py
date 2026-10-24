from datetime import datetime
from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReasoningEffort = Literal["low", "medium", "high"]
AgentType = Literal["default", "whatsapp_agent"]


def _clean_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("base_url deve ser uma URL http(s) completa, ex.: http://localhost:5580")
    if "@" in parsed.netloc:
        raise ValueError("base_url nao pode conter usuario ou senha (userinfo)")
    return value


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("name nao pode ser vazio")
    return value


class GatewayModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(..., min_length=1, max_length=200)
    reasoning_effort: Optional[ReasoningEffort] = None
    max_tokens: Optional[int] = Field(None, ge=1, le=200_000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    supports_tools: bool = True
    is_active: bool = True


class GatewayModelCreate(GatewayModelBase):
    pass


class GatewayModelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_id: Optional[str] = Field(None, min_length=1, max_length=200)
    reasoning_effort: Optional[ReasoningEffort] = None
    max_tokens: Optional[int] = Field(None, ge=1, le=200_000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    supports_tools: Optional[bool] = None
    is_active: Optional[bool] = None


class GatewayModelResponse(GatewayModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gateway_id: str
    created_at: Optional[datetime] = None


class GatewayCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    timeout_seconds: int = Field(60, ge=1, le=900)
    is_active: bool = True

    _check_url = field_validator("base_url")(_clean_base_url)
    _check_name = field_validator("name")(_clean_name)


class GatewayUpdate(BaseModel):
    """`api_key` ausente = manter; string vazia = remover; valor = substituir."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=900)
    is_active: Optional[bool] = None

    @field_validator("base_url")
    @classmethod
    def _check_url(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_base_url(value)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_name(value)


class GatewayResponse(BaseModel):
    """A chave de API nunca e devolvida; apenas `has_api_key`."""

    id: str
    name: str
    base_url: str
    has_api_key: bool
    timeout_seconds: int
    is_active: bool
    models: List[GatewayModelResponse] = []
    created_at: Optional[datetime] = None


class AssignmentUpdate(BaseModel):
    gateway_model_id: str


class AssignmentResponse(BaseModel):
    agent_type: AgentType
    gateway_model_id: str
    gateway_id: str
    gateway_name: str
    model_name: str
    model_id: str


class ActiveModelResponse(BaseModel):
    """Leitura enxuta para usuário comum: sem `base_url`, ids nem chave."""

    agent_type: AgentType
    gateway_name: str
    model_name: str


class RemoteModelsResponse(BaseModel):
    models: List[str]


class ProbeResponse(BaseModel):
    ok: bool
    latency_ms: Optional[int] = None
    content: Optional[str] = None
    thinking: Optional[bool] = None
    error: Optional[str] = None
