from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.models import Product
from app.schemas.product import ProductCreate, ProductUpdate


def create_product(db: Session, product: ProductCreate) -> Product:
    """Create a new product"""
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def get_product(db: Session, product_id: str) -> Optional[Product]:
    """Get product by ID"""
    return db.query(Product).filter(Product.id == product_id).first()


def get_products_by_company(db: Session, company_id: str, skip: int = 0, limit: int = 100) -> List[Product]:
    """Get all products for a specific company"""
    return db.query(Product).filter(
        Product.company_id == company_id,
        Product.is_available == True
    ).offset(skip).limit(limit).all()


def list_products(db: Session, skip: int = 0, limit: int = 100) -> List[Product]:
    """List all products with pagination"""
    return db.query(Product).filter(Product.is_available == True).offset(skip).limit(limit).all()


def update_product(db: Session, product_id: str, product_update: ProductUpdate) -> Optional[Product]:
    """Update product"""
    db_product = get_product(db, product_id)
    if not db_product:
        return None

    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)

    db.commit()
    db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: str) -> bool:
    """Soft delete product (set is_available to False)"""
    db_product = get_product(db, product_id)
    if not db_product:
        return False

    db_product.is_available = False
    db.commit()
    return True
