from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class ProductType(Base):
    # DEPRECATED: Use MenuItem/MenuCategory instead for inventory management
    __tablename__ = "product_types"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    products = relationship("Product", back_populates="product_type")


class Product(Base):
    # DEPRECATED: Use MenuItem/MenuCategory instead for inventory management
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    product_type_id = Column(String, ForeignKey("product_types.id"))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    image_url = Column(String(500))
    sku = Column(String(50), unique=True, index=True)
    is_available = Column(Boolean, default=True)
    stock_quantity = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="products")
    product_type = relationship("ProductType", back_populates="products")


class MenuCatalog(Base):
    __tablename__ = "menu_catalogs"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), default="json")
    source_file = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_menu_catalog_company_name"),
    )

    company = relationship("Company", back_populates="menu_catalogs")
    categories = relationship("MenuCategory", back_populates="catalog", cascade="all, delete-orphan")
    items = relationship("MenuItem", back_populates="catalog", cascade="all, delete-orphan")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(String, primary_key=True, default=generate_uuid)
    catalog_id = Column(String, ForeignKey("menu_catalogs.id"), nullable=False, index=True)
    external_id = Column(String(100), index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    raw_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("catalog_id", "external_id", name="uq_menu_category_catalog_external"),
    )

    catalog = relationship("MenuCatalog", back_populates="categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    catalog_id = Column(String, ForeignKey("menu_catalogs.id"), nullable=False, index=True)
    category_id = Column(String, ForeignKey("menu_categories.id"), nullable=False, index=True)
    external_id = Column(String(100), index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2))
    image_url = Column(String(500))
    is_available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    custom_attributes = Column(JSONB, default=list, nullable=False)
    raw_payload = Column(JSONB)
    sku = Column(String(50), unique=True, index=True, nullable=True)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("catalog_id", "external_id", name="uq_menu_item_catalog_external"),
    )

    catalog = relationship("MenuCatalog", back_populates="items")
    category = relationship("MenuCategory", back_populates="items")


# ============== WhatsApp Agent Models ==============
