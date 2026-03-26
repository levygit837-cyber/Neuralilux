from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ProductCreate(BaseModel):
    company_id: str
    product_type_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    image_url: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    is_available: bool = True
    stock_quantity: Optional[int] = Field(None, ge=0)


class ProductUpdate(BaseModel):
    product_type_id: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    image_url: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    is_available: Optional[bool] = None
    stock_quantity: Optional[int] = Field(None, ge=0)


class ProductResponse(BaseModel):
    id: str
    company_id: str
    product_type_id: str
    name: str
    description: Optional[str] = None
    price: Decimal
    image_url: Optional[str] = None
    sku: Optional[str] = None
    is_available: bool
    stock_quantity: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
