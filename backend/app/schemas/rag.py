"""Pydantic schemas for RAG rules."""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class RuleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: str = Field(default="general")


class RuleCreate(RuleBase):
    company_id: Optional[str] = None


class RuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    is_active: Optional[bool] = None


class RuleResponse(RuleBase):
    id: str
    company_id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    rules: list[RuleResponse]
    total: int


class DocumentIndexRequest(BaseModel):
    company_id: str
    title: str
    content: str
    category: str = "general"


class DocumentIndexResponse(BaseModel):
    success: bool
    document_id: str
    message: str
