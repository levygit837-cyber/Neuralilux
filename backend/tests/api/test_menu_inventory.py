from app.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu.inventory import (
    get_menu_item,
    get_menu_items_by_company,
    list_menu_items,
    soft_delete_menu_item,
)


def test_get_menu_item(db):
    """Test getting a menu item by ID."""
    company = Company(name="Test Company", is_active=True)
    db.add(company)
    db.commit()
    
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    
    category = MenuCategory(
        catalog_id=catalog.id,
        name="Bebidas",
    )
    db.add(category)
    db.commit()
    
    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Coca-Cola",
        price=5.0,
        sku="COCA-001",
        stock_quantity=50,
    )
    db.add(item)
    db.commit()
    
    retrieved = get_menu_item(db, item.id)
    assert retrieved is not None
    assert retrieved.name == "Coca-Cola"
    assert retrieved.sku == "COCA-001"


def test_get_menu_item_not_found(db):
    """Test getting a non-existent menu item."""
    retrieved = get_menu_item(db, "non-existent-id")
    assert retrieved is None


def test_get_menu_items_by_company(db):
    """Test getting menu items by company."""
    company = Company(name="Test Company", is_active=True)
    db.add(company)
    db.commit()
    
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    
    category = MenuCategory(
        catalog_id=catalog.id,
        name="Bebidas",
    )
    db.add(category)
    db.commit()
    
    # Add available items
    for i in range(3):
        item = MenuItem(
            catalog_id=catalog.id,
            category_id=category.id,
            name=f"Produto {i}",
            price=10.0,
            is_available=True,
        )
        db.add(item)
    
    # Add unavailable item
    unavailable = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Indisponível",
        price=15.0,
        is_available=False,
    )
    db.add(unavailable)
    db.commit()
    
    # Get only available items
    items = get_menu_items_by_company(db, company.id, only_available=True)
    assert len(items) == 3
    
    # Get all items
    all_items = get_menu_items_by_company(db, company.id, only_available=False)
    assert len(all_items) == 4


def test_list_menu_items(db):
    """Test listing menu items with pagination."""
    # Create items
    for i in range(5):
        item = MenuItem(
            catalog_id="catalog-1",
            category_id="category-1",
            name=f"Produto {i}",
            price=10.0,
            is_available=True,
        )
        db.add(item)
    db.commit()
    
    # Get with pagination
    items = list_menu_items(db, skip=0, limit=3)
    assert len(items) == 3
    
    # Get next page
    items_page2 = list_menu_items(db, skip=3, limit=3)
    assert len(items_page2) == 2


def test_soft_delete_menu_item(db):
    """Test soft deleting a menu item (setting is_available to False)."""
    company = Company(name="Test Company", is_active=True)
    db.add(company)
    db.commit()
    
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    
    category = MenuCategory(
        catalog_id=catalog.id,
        name="Bebidas",
    )
    db.add(category)
    db.commit()
    
    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Coca-Cola",
        price=5.0,
        is_available=True,
    )
    db.add(item)
    db.commit()
    
    # Soft delete
    result = soft_delete_menu_item(db, item.id)
    assert result is True
    
    # Verify item still exists but is unavailable
    db.refresh(item)
    assert item.is_available is False


def test_soft_delete_menu_item_not_found(db):
    """Test soft deleting a non-existent menu item."""
    result = soft_delete_menu_item(db, "non-existent-id")
    assert result is False
