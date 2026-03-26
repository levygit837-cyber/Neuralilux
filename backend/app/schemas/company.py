from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime


class BusinessHours(BaseModel):
    open: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    close: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    closed: bool = False


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    business_type_id: str
    description: Optional[str] = None
    logo_url: Optional[str] = None

    # Address
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = Field(None, max_length=2)
    address_zip: Optional[str] = None

    # Contacts
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None

    # Business hours
    business_hours: Optional[Dict[str, Any]] = None

    # AI Configuration
    ai_system_prompt: Optional[str] = None
    ai_model: str = "gpt-4-turbo-preview"
    ai_temperature: int = Field(70, ge=0, le=100)
    ai_max_tokens: int = Field(1000, ge=100, le=4000)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    business_type_id: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None

    # Address
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = Field(None, max_length=2)
    address_zip: Optional[str] = None

    # Contacts
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None

    # Business hours
    business_hours: Optional[Dict[str, Any]] = None

    # AI Configuration
    ai_system_prompt: Optional[str] = None
    ai_model: Optional[str] = None
    ai_temperature: Optional[int] = Field(None, ge=0, le=100)
    ai_max_tokens: Optional[int] = Field(None, ge=100, le=4000)

    is_active: Optional[bool] = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    business_type_id: str
    description: Optional[str] = None
    logo_url: Optional[str] = None

    # Address
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None

    # Contacts
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None

    # Business hours
    business_hours: Optional[Dict[str, Any]] = None

    # AI Configuration
    ai_system_prompt: Optional[str] = None
    ai_model: str
    ai_temperature: int
    ai_max_tokens: int

    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
