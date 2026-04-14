"""Inventory management tools for the Super Agent.

Provides CRUD operations for product categories and items with proper validation.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import MenuCatalog, MenuCategory, MenuItem, User


def _verify_user_company(db: Session, user_id: str, company_id: str) -> None:
    """Verify that a user belongs to the specified company."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    if user.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não pertence a esta empresa",
        )


def _get_db_session(db_session: Optional[Session] = None) -> Session:
    """Get database session from parameter or create new one."""
    if db_session is not None:
        return db_session
    db_gen = get_db()
    return next(db_gen)


def _get_active_catalog(db: Session, company_id: str) -> MenuCatalog:
    """Get the active catalog for a company."""
    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
        .order_by(MenuCatalog.created_at.desc())
        .first()
    )
    if not catalog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catálogo ativo não encontrado para esta empresa",
        )
    return catalog


def _get_category_for_company(db: Session, company_id: str, category_id: str) -> MenuCategory:
    """Get a category verifying it belongs to the company's active catalog."""
    category = (
        db.query(MenuCategory)
        .join(MenuCatalog, MenuCategory.catalog_id == MenuCatalog.id)
        .filter(
            MenuCategory.id == category_id,
            MenuCatalog.company_id == company_id,
            MenuCatalog.is_active == True,
        )
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada ou não pertence a esta empresa",
        )
    return category


def _get_item_for_company(db: Session, company_id: str, item_id: str) -> MenuItem:
    """Get an item verifying it belongs to the company's active catalog."""
    item = (
        db.query(MenuItem)
        .join(MenuCatalog, MenuItem.catalog_id == MenuCatalog.id)
        .filter(
            MenuItem.id == item_id,
            MenuCatalog.company_id == company_id,
            MenuCatalog.is_active == True,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado ou não pertence a esta empresa",
        )
    return item


def _check_category_stock(db: Session, category_id: str) -> List[Dict[str, Any]]:
    """Check if a category has items with stock > 0."""
    items_with_stock = (
        db.query(MenuItem)
        .filter(MenuItem.category_id == category_id, MenuItem.stock_quantity > 0)
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "stock_quantity": item.stock_quantity,
        }
        for item in items_with_stock
    ]


def _check_item_stock(db: Session, item_id: str) -> Optional[int]:
    """Check if an item has stock > 0. Returns stock quantity or None if no stock."""
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        return None
    return item.stock_quantity if item.stock_quantity > 0 else None


def list_product_categories(
    company_id: str,
    user_id: str,
    limit: int = 50,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """List all categories in the company's active catalog."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        catalog = _get_active_catalog(db, company_id)
        
        categories = (
            db.query(MenuCategory)
            .filter(MenuCategory.catalog_id == catalog.id)
            .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
            .limit(limit)
            .all()
        )
        
        # Get item counts for each category
        category_ids = [cat.id for cat in categories]
        items = (
            db.query(MenuItem)
            .filter(MenuItem.category_id.in_(category_ids))
            .all()
        )
        item_counts = Counter(item.category_id for item in items)
        
        serialized_categories = [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "sort_order": cat.sort_order or 0,
                "items_count": item_counts.get(cat.id, 0),
            }
            for cat in categories
        ]
        
        return {
            "catalog_id": catalog.id,
            "catalog_name": catalog.name,
            "categories": serialized_categories,
            "total_categories": len(serialized_categories),
        }
    finally:
        if should_close and db is not None:
            db.close()


def list_products_by_category(
    company_id: str,
    user_id: str,
    category_id: str,
    limit: int = 20,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """List products in a specific category."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        category = _get_category_for_company(db, company_id, category_id)
        
        items = (
            db.query(MenuItem)
            .filter(MenuItem.category_id == category_id)
            .order_by(MenuItem.sort_order.asc(), MenuItem.name.asc())
            .limit(limit)
            .all()
        )
        
        serialized_items = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else None,
                "is_available": bool(item.is_available),
                "sku": item.sku,
                "stock_quantity": item.stock_quantity or 0,
                "image_url": item.image_url,
            }
            for item in items
        ]
        
        return {
            "category_id": category_id,
            "category_name": category.name,
            "items": serialized_items,
            "total_items": len(serialized_items),
        }
    finally:
        if should_close and db is not None:
            db.close()


def search_product_in_category(
    company_id: str,
    user_id: str,
    category_id: str,
    product_name: str,
    limit: int = 10,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Search for a product by name in a specific category."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        category = _get_category_for_company(db, company_id, category_id)
        
        items = (
            db.query(MenuItem)
            .filter(
                MenuItem.category_id == category_id,
                MenuItem.name.ilike(f"%{product_name}%")
            )
            .order_by(MenuItem.name.asc())
            .limit(limit)
            .all()
        )
        
        serialized_items = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else None,
                "is_available": bool(item.is_available),
                "sku": item.sku,
                "stock_quantity": item.stock_quantity or 0,
            }
            for item in items
        ]
        
        return {
            "category_id": category_id,
            "category_name": category.name,
            "search_term": product_name,
            "items": serialized_items,
            "total_items": len(serialized_items),
        }
    finally:
        if should_close and db is not None:
            db.close()


def create_product_category(
    company_id: str,
    user_id: str,
    name: str,
    description: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Create a new product category."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        catalog = _get_active_catalog(db, company_id)
        
        # Check for duplicate name
        existing = (
            db.query(MenuCategory)
            .filter(MenuCategory.catalog_id == catalog.id, MenuCategory.name == name.strip())
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma categoria com esse nome",
            )
        
        # Get next sort_order
        last_sort_order = (
            db.query(MenuCategory.sort_order)
            .filter(MenuCategory.catalog_id == catalog.id)
            .order_by(MenuCategory.sort_order.desc())
            .first()
        )
        next_sort_order = (last_sort_order[0] if last_sort_order and last_sort_order[0] is not None else 0) + 1
        
        category = MenuCategory(
            catalog_id=catalog.id,
            name=name.strip(),
            description=description.strip() if description else None,
            sort_order=next_sort_order,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        
        return {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "sort_order": category.sort_order,
            "items_count": 0,
        }
    finally:
        if should_close and db is not None:
            db.close()


def create_product(
    company_id: str,
    user_id: str,
    category_id: str,
    name: str,
    description: Optional[str] = None,
    price: Optional[Decimal] = None,
    sku: Optional[str] = None,
    stock_quantity: int = 0,
    is_available: bool = True,
    image_url: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Create a new product in a category."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        catalog = _get_active_catalog(db, company_id)
        category = _get_category_for_company(db, company_id, category_id)
        
        # Validate SKU uniqueness if provided
        if sku:
            existing_sku = (
                db.query(MenuItem)
                .filter(MenuItem.catalog_id == catalog.id, MenuItem.sku == sku.strip())
                .first()
            )
            if existing_sku:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe um item com esse SKU",
                )
        
        # Get next sort_order
        last_sort_order = (
            db.query(MenuItem.sort_order)
            .filter(MenuItem.category_id == category.id)
            .order_by(MenuItem.sort_order.desc())
            .first()
        )
        next_sort_order = (last_sort_order[0] if last_sort_order and last_sort_order[0] is not None else 0) + 1
        
        item = MenuItem(
            catalog_id=catalog.id,
            category_id=category.id,
            name=name.strip(),
            description=description.strip() if description else None,
            price=price,
            is_available=is_available,
            sku=sku.strip() if sku else None,
            stock_quantity=stock_quantity or 0,
            image_url=image_url,
            sort_order=next_sort_order,
            custom_attributes=[],
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": float(item.price) if item.price else None,
            "is_available": bool(item.is_available),
            "sku": item.sku,
            "stock_quantity": item.stock_quantity or 0,
            "image_url": item.image_url,
            "category_id": category_id,
        }
    finally:
        if should_close and db is not None:
            db.close()


def update_product(
    company_id: str,
    user_id: str,
    product_id: str,
    category_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price: Optional[Decimal] = None,
    sku: Optional[str] = None,
    stock_quantity: Optional[int] = None,
    is_available: Optional[bool] = None,
    image_url: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Update an existing product."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        catalog = _get_active_catalog(db, company_id)
        item = _get_item_for_company(db, company_id, product_id)
        
        # Update category if provided
        if category_id:
            new_category = _get_category_for_company(db, company_id, category_id)
            item.category_id = new_category.id
        
        # Update name if provided
        if name:
            item.name = name.strip()
        
        # Update description if provided
        if description is not None:
            item.description = description.strip() if description else None
        
        # Update price if provided
        if price is not None:
            item.price = price
        
        # Update availability if provided
        if is_available is not None:
            item.is_available = is_available
        
        # Update SKU if provided
        if sku is not None:
            if sku.strip() and sku.strip() != item.sku:
                existing_sku = (
                    db.query(MenuItem)
                    .filter(
                        MenuItem.catalog_id == catalog.id,
                        MenuItem.sku == sku.strip(),
                        MenuItem.id != product_id,
                    )
                    .first()
                )
                if existing_sku:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Já existe um item com esse SKU",
                    )
            item.sku = sku.strip() if sku else None
        
        # Update stock quantity if provided
        if stock_quantity is not None:
            item.stock_quantity = stock_quantity or 0
        
        # Update image URL if provided
        if image_url is not None:
            item.image_url = image_url
        
        db.commit()
        db.refresh(item)
        
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": float(item.price) if item.price else None,
            "is_available": bool(item.is_available),
            "sku": item.sku,
            "stock_quantity": item.stock_quantity or 0,
            "image_url": item.image_url,
            "category_id": item.category_id,
        }
    finally:
        if should_close and db is not None:
            db.close()


def delete_product_category(
    company_id: str,
    user_id: str,
    category_id: str,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Delete a product category and all its products."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        category = _get_category_for_company(db, company_id, category_id)
        
        # Check for items with stock
        items_with_stock = _check_category_stock(db, category_id)
        if items_with_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Não é possível excluir categoria com itens em estoque",
                    "items_with_stock": items_with_stock,
                },
            )
        
        # Delete all items in the category
        db.query(MenuItem).filter(MenuItem.category_id == category_id).delete(
            synchronize_session=False
        )
        
        # Delete the category
        db.delete(category)
        db.commit()
        
        return {
            "category_id": category_id,
            "category_name": category.name,
            "deleted": True,
        }
    finally:
        if should_close and db is not None:
            db.close()


def delete_product(
    company_id: str,
    user_id: str,
    product_id: str,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Delete a product."""
    db: Optional[Session] = None
    should_close = db_session is None
    try:
        db = _get_db_session(db_session)
        
        _verify_user_company(db, user_id, company_id)
        item = _get_item_for_company(db, company_id, product_id)
        
        # Check for stock
        stock = _check_item_stock(db, product_id)
        if stock is not None and stock > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível excluir item com estoque ({stock} unidades)",
            )
        
        item_name = item.name
        db.delete(item)
        db.commit()
        
        return {
            "product_id": product_id,
            "product_name": item_name,
            "deleted": True,
        }
    finally:
        if should_close and db is not None:
            db.close()
