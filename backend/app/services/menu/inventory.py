"""Consultas de estoque sobre os Catalog Items (listagem, busca por Company e baixa lógica)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import MenuCatalog, MenuItem


def get_menu_item(db: Session, item_id: str) -> Optional[MenuItem]:
    """Get a menu item by ID."""
    return db.query(MenuItem).filter(MenuItem.id == item_id).first()


def get_menu_items_by_company(
    db: Session,
    company_id: str,
    skip: int = 0,
    limit: int = 100,
    only_available: bool = True,
) -> list[MenuItem]:
    """Get all menu items for a specific company."""
    query = (
        db.query(MenuItem)
        .join(MenuCatalog, MenuItem.catalog_id == MenuCatalog.id)
        .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
    )
    
    if only_available:
        query = query.filter(MenuItem.is_available == True)
    
    return query.offset(skip).limit(limit).all()


def list_menu_items(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    only_available: bool = True,
) -> list[MenuItem]:
    """List all menu items with pagination."""
    query = db.query(MenuItem)
    
    if only_available:
        query = query.filter(MenuItem.is_available == True)
    
    return query.offset(skip).limit(limit).all()


def soft_delete_menu_item(db: Session, item_id: str) -> bool:
    """Soft delete menu item (set is_available to False instead of deleting)."""
    item = get_menu_item(db, item_id)
    if not item:
        return False
    
    item.is_available = False
    db.commit()
    return True
