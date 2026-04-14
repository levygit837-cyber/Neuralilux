"""Tests for inventory management tools for the Super Agent."""
import pytest
from app.models.models import Company, MenuCatalog, MenuCategory, MenuItem, User
from app.super_agents.tools.inventory_tool import (
    create_product,
    create_product_category,
    delete_product,
    delete_product_category,
    list_product_categories,
    list_products_by_category,
    search_product_in_category,
    update_product,
)
from app.core.database import get_db
from app.core.security import get_password_hash


def _setup_test_company(db):
    """Create a test company and user."""
    company = Company(name="Test Company", is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    
    user = User(
        email=f"{company.id}@test.com",
        full_name="Test User",
        company_id=company.id,
        hashed_password=get_password_hash("testpass123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return company, user


def _setup_catalog_and_category(db, company):
    """Create a catalog and category for testing."""
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    
    category = MenuCategory(
        catalog_id=catalog.id,
        name="Bebidas",
        description="Bebidas geladas",
        sort_order=1,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    
    return catalog, category


def test_list_product_categories_empty(db):
    """Test listing categories when catalog has no categories."""
    company, user = _setup_test_company(db)
    
    # Create catalog manually
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    
    result = list_product_categories(
        company_id=company.id,
        user_id=user.id,
        db_session=db,
    )
    
    assert result["catalog_id"] == catalog.id
    assert result["catalog_name"] == "Cardápio"
    assert result["categories"] == []
    assert result["total_categories"] == 0


def test_list_product_categories_with_items(db):
    """Test listing categories with item counts."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Add items
    for i in range(3):
        item = MenuItem(
            catalog_id=catalog.id,
            category_id=category.id,
            name=f"Produto {i}",
            price=10.0,
            sku=f"SKU-{i}",
            stock_quantity=i + 1,
        )
        db.add(item)
    db.commit()
    
    result = list_product_categories(
        company_id=company.id,
        user_id=user.id,
        db_session=db,
    )
    
    assert result["catalog_id"] == catalog.id
    assert len(result["categories"]) == 1
    assert result["categories"][0]["name"] == "Bebidas"
    assert result["categories"][0]["items_count"] == 3


def test_list_products_by_category(db):
    """Test listing products in a category."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Add items
    items = []
    for i in range(3):
        item = MenuItem(
            catalog_id=catalog.id,
            category_id=category.id,
            name=f"Produto {i}",
            price=10.0 + i,
            sku=f"SKU-{i}",
            stock_quantity=i + 1,
        )
        db.add(item)
        items.append(item)
    db.commit()
    
    result = list_products_by_category(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        db_session=db,
    )
    
    assert result["category_id"] == category.id
    assert result["category_name"] == "Bebidas"
    assert len(result["items"]) == 3
    assert result["items"][0]["name"] == "Produto 0"
    assert result["items"][0]["sku"] == "SKU-0"
    assert result["items"][0]["stock_quantity"] == 1


def test_search_product_in_category(db):
    """Test searching for a product by name."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Add items
    item1 = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Coca-Cola",
        price=5.0,
        sku="COCA-001",
        stock_quantity=10,
    )
    item2 = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Pepsi",
        price=4.5,
        sku="PEPSI-001",
        stock_quantity=5,
    )
    db.add(item1)
    db.add(item2)
    db.commit()
    
    result = search_product_in_category(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        product_name="coca",
        db_session=db,
    )
    
    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == "Coca-Cola"
    assert result["items"][0]["sku"] == "COCA-001"


def test_create_product_category(db):
    """Test creating a new category."""
    company, user = _setup_test_company(db)
    catalog = MenuCatalog(
        company_id=company.id,
        name="Cardápio",
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    
    result = create_product_category(
        company_id=company.id,
        user_id=user.id,
        name="Lanches",
        description="Hambúrgueres e sanduíches",
        db_session=db,
    )
    
    assert result["name"] == "Lanches"
    assert result["description"] == "Hambúrgueres e sanduíches"
    assert result["items_count"] == 0
    assert result["sort_order"] == 1
    
    # Verify in DB
    category = db.query(MenuCategory).filter(MenuCategory.name == "Lanches").one()
    assert category.description == "Hambúrgueres e sanduíches"


def test_create_product_category_duplicate_name(db):
    """Test that duplicate category names are rejected."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    with pytest.raises(Exception) as exc_info:
        create_product_category(
            company_id=company.id,
            user_id=user.id,
            name="Bebidas",  # Duplicate name
            db_session=db,
        )
    
    assert "Já existe uma categoria com esse nome" in str(exc_info.value)


def test_create_product(db):
    """Test creating a new product."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    result = create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="X-Burger",
        description="Pão, carne e queijo",
        price=24.90,
        sku="XBURGER-001",
        stock_quantity=10,
        is_available=True,
        db_session=db,
    )
    
    assert result["name"] == "X-Burger"
    assert result["description"] == "Pão, carne e queijo"
    assert result["price"] == 24.90
    assert result["sku"] == "XBURGER-001"
    assert result["stock_quantity"] == 10
    assert result["is_available"] is True
    
    # Verify in DB
    item = db.query(MenuItem).filter(MenuItem.name == "X-Burger").one()
    assert item.sku == "XBURGER-001"
    assert item.stock_quantity == 10


def test_create_product_duplicate_sku(db):
    """Test that duplicate SKUs are rejected."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Create first product with SKU
    create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto 1",
        price=10.0,
        sku="SKU-001",
        db_session=db,
    )
    
    # Try to create second product with same SKU
    with pytest.raises(Exception) as exc_info:
        create_product(
            company_id=company.id,
            user_id=user.id,
            category_id=category.id,
            name="Produto 2",
            price=15.0,
            sku="SKU-001",  # Duplicate SKU
            db_session=db,
        )
    
    assert "Já existe um item com esse SKU" in str(exc_info.value)


def test_update_product(db):
    """Test updating an existing product."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Create product
    created = create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto Original",
        price=10.0,
        sku="SKU-001",
        stock_quantity=5,
        db_session=db,
    )
    
    # Update product
    result = update_product(
        company_id=company.id,
        user_id=user.id,
        product_id=created["id"],
        name="Produto Atualizado",
        price=15.0,
        stock_quantity=20,
        db_session=db,
    )
    
    assert result["name"] == "Produto Atualizado"
    assert result["price"] == 15.0
    assert result["stock_quantity"] == 20
    assert result["sku"] == "SKU-001"  # SKU unchanged


def test_update_product_sku(db):
    """Test updating product SKU with uniqueness validation."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Create two products
    prod1 = create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto 1",
        price=10.0,
        sku="SKU-001",
        db_session=db,
    )
    create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto 2",
        price=15.0,
        sku="SKU-002",
        db_session=db,
    )
    
    # Try to update product 1 with SKU of product 2
    with pytest.raises(Exception) as exc_info:
        update_product(
            company_id=company.id,
            user_id=user.id,
            product_id=prod1["id"],
            sku="SKU-002",  # Already used by product 2
            db_session=db,
        )
    
    assert "Já existe um item com esse SKU" in str(exc_info.value)


def test_delete_product_category(db):
    """Test deleting a category and its products."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Add items with no stock
    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Produto",
        price=10.0,
        stock_quantity=0,
    )
    db.add(item)
    db.commit()
    
    result = delete_product_category(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        db_session=db,
    )
    
    assert result["deleted"] is True
    assert result["category_name"] == "Bebidas"
    
    # Verify deletion
    assert db.query(MenuCategory).filter(MenuCategory.id == category.id).count() == 0
    assert db.query(MenuItem).filter(MenuItem.category_id == category.id).count() == 0


def test_delete_product_category_with_stock(db):
    """Test that category deletion is blocked when items have stock."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    # Add item with stock
    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Produto",
        price=10.0,
        stock_quantity=5,  # Has stock
    )
    db.add(item)
    db.commit()
    
    with pytest.raises(Exception) as exc_info:
        delete_product_category(
            company_id=company.id,
            user_id=user.id,
            category_id=category.id,
            db_session=db,
        )
    
    assert "estoque" in str(exc_info.value).lower()


def test_delete_product(db):
    """Test deleting a product."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    created = create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto",
        price=10.0,
        stock_quantity=0,
        db_session=db,
    )
    
    result = delete_product(
        company_id=company.id,
        user_id=user.id,
        product_id=created["id"],
        db_session=db,
    )
    
    assert result["deleted"] is True
    assert result["product_name"] == "Produto"
    
    # Verify deletion
    assert db.query(MenuItem).filter(MenuItem.id == created["id"]).count() == 0


def test_delete_product_with_stock(db):
    """Test that product deletion is blocked when it has stock."""
    company, user = _setup_test_company(db)
    catalog, category = _setup_catalog_and_category(db, company)
    
    created = create_product(
        company_id=company.id,
        user_id=user.id,
        category_id=category.id,
        name="Produto",
        price=10.0,
        stock_quantity=10,  # Has stock
        db_session=db,
    )
    
    with pytest.raises(Exception) as exc_info:
        delete_product(
            company_id=company.id,
            user_id=user.id,
            product_id=created["id"],
            db_session=db,
        )
    
    assert "estoque" in str(exc_info.value).lower()


def test_user_permission_validation(db):
    """Test that users from other companies cannot access inventory."""
    company1, user1 = _setup_test_company(db)
    company2, user2 = _setup_test_company(db)
    
    catalog, category = _setup_catalog_and_category(db, company1)
    
    # User from company2 tries to access company1's categories
    with pytest.raises(Exception) as exc_info:
        list_product_categories(
            company_id=company1.id,
            user_id=user2.id,  # Wrong user
            db_session=db,
        )
    
    assert "não pertence" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
