from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.agent.clock import DEFAULT_TIMEZONE
from app.models.company import DEFAULT_SESSION_TIMEOUT_MINUTES
from app.schemas.company_fields import (
    MINIMUM_ORDER_MAX,
    blank_to_none,
    reject_bool,
    validate_business_hours,
    validate_phone,
    validate_pix_key,
)

# Texto livre do cadastro: vazio limpa o campo (os limites seguem as colunas de `companies`).
_TEXT_FIELDS = (
    "description",
    "logo_url",
    "address_street",
    "address_number",
    "address_complement",
    "address_neighborhood",
    "address_city",
    "address_state",
    "address_zip",
    "email",
    "whatsapp",
)
_NOT_NULL_FIELDS = ("timezone", "session_timeout_minutes", "handoff_timeout_hours")


def _loadable_timezone(value: object) -> str:
    """Só aceita um fuso que o `ZoneInfo` carrega; `None`, vazio e caminhos ("../x") são recusados."""
    try:
        ZoneInfo(value)  # type: ignore[arg-type]
    except (ZoneInfoNotFoundError, ValueError, TypeError, OSError):
        raise ValueError("Fuso horário inválido; use um nome IANA, como America/Sao_Paulo.") from None
    return value  # type: ignore[return-value]


class CompanySettings(BaseModel):
    """Campos de configuração que o painel edita; todos opcionais (campo ausente = não muda)."""

    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)

    # Endereço
    address_street: Optional[str] = Field(None, max_length=200)
    address_number: Optional[str] = Field(None, max_length=20)
    address_complement: Optional[str] = Field(None, max_length=100)
    address_neighborhood: Optional[str] = Field(None, max_length=100)
    address_city: Optional[str] = Field(None, max_length=100)
    address_state: Optional[str] = Field(None, max_length=2)
    address_zip: Optional[str] = Field(None, max_length=10)

    # Contato e pagamento
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = Field(None, max_length=20)
    pix_key: Optional[str] = None
    minimum_order: Optional[Decimal] = Field(
        None, ge=0, le=MINIMUM_ORDER_MAX, max_digits=10, decimal_places=2, allow_inf_nan=False
    )

    # Atendimento
    business_hours: Optional[dict[str, Any]] = None
    timezone: Optional[str] = None
    session_timeout_minutes: Optional[int] = Field(None, ge=1, le=10080)  # ADR 0007
    handoff_timeout_hours: Optional[int] = Field(None, ge=1, le=720)

    _blank_text = field_validator(*_TEXT_FIELDS, mode="before")(blank_to_none)
    _check_phone = field_validator("phone", mode="before")(validate_phone)
    # `True` viraria 1 (bool é int no Python): número de verdade ou 422.
    _no_bool = field_validator(
        "minimum_order", "session_timeout_minutes", "handoff_timeout_hours", mode="before"
    )(reject_bool)
    _check_hours = field_validator("business_hours")(validate_business_hours)
    _check_pix = field_validator("pix_key", mode="before")(validate_pix_key)
    _check_timezone = field_validator("timezone")(_loadable_timezone)

    @field_validator(*_NOT_NULL_FIELDS[1:], mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        # A coluna não aceita NULL: se o campo veio no corpo, tem de ter valor.
        if value is None:
            raise ValueError("Informe um valor.")
        return value


class CompanyCreate(CompanySettings):
    name: str = Field(..., min_length=1, max_length=200)
    business_type_id: str
    timezone: str = DEFAULT_TIMEZONE
    session_timeout_minutes: int = Field(DEFAULT_SESSION_TIMEOUT_MINUTES, ge=1, le=10080)
    handoff_timeout_hours: int = Field(4, ge=1, le=720)


class CompanyUpdate(CompanySettings):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    business_type_id: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def _name_required(cls, value: object) -> object:
        value = value.strip() if isinstance(value, str) else value
        if not value:
            raise ValueError("O nome da empresa não pode ficar vazio.")
        return value


class CompanyResponse(BaseModel):
    id: str
    name: str
    business_type_id: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None

    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None

    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    pix_key: Optional[str] = None
    minimum_order: Optional[float] = None

    business_hours: Optional[dict[str, Any]] = None
    timezone: str = DEFAULT_TIMEZONE
    session_timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES
    handoff_timeout_hours: int = 4

    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentSettings(BaseModel):
    """Ajustes de resposta do Agent da Company; o modelo vem do Gateway atribuído."""

    temperature: Optional[float] = Field(None, ge=0, le=1)  # None: usa a do Gateway
    max_tokens: int = Field(1000, ge=100, le=4000)


class AgentSettingsUpdate(BaseModel):
    temperature: Optional[float] = Field(None, ge=0, le=1)
    max_tokens: Optional[int] = Field(None, ge=100, le=4000)

    @field_validator("max_tokens", mode="before")
    @classmethod
    def _max_tokens_not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Informe um valor.")
        return value
