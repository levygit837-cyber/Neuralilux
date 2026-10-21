from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.base import PaginationParams


class ContactCreate(BaseModel):
    instance_id: str
    phone_number: str = Field(..., min_length=10, max_length=20)
    remote_jid: str
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_blocked: Optional[bool] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    instance_id: str
    phone_number: str
    remote_jid: str
    name: Optional[str] = None
    push_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_blocked: bool
    is_business: bool
    last_seen: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContactFilter(PaginationParams):
    instance_id: Optional[str] = None
    is_blocked: Optional[bool] = None
    is_business: Optional[bool] = None
    search: Optional[str] = None  # Search by name or phone number


class PaginatedContacts(BaseModel):
    items: List[ContactResponse]
    total: int
    skip: int
    limit: int
