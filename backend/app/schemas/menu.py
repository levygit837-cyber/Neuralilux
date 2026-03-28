from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class MenuAttributeInput(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=500)


class MenuCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class MenuItemCreate(BaseModel):
    category_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    is_available: bool = True
    custom_attributes: List[MenuAttributeInput] = Field(default_factory=list)


class MenuItemUpdate(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    is_available: Optional[bool] = None
    custom_attributes: Optional[List[MenuAttributeInput]] = None


class MenuCatalogResponse(BaseModel):
    id: str
    name: str
    source_type: Optional[str] = None


class MenuCategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sort_order: int
    items_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuItemResponse(BaseModel):
    id: str
    category_id: str
    name: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    is_available: bool
    custom_attributes: List[MenuAttributeInput] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuManagementResponse(BaseModel):
    catalog: MenuCatalogResponse
    categories: List[MenuCategoryResponse]
    items: List[MenuItemResponse]
