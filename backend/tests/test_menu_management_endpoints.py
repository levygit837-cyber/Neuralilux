from app.models.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu_management_service import (
    get_menu_item,
    get_menu_items_by_company,
    list_menu_items,
    soft_delete_menu_item,
)


def _auth_headers_for_company(client, db, company_name: str = "Empresa Estoque"):
    company = Company(name=company_name, is_active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    company_id = company.id

    email = f"{company_id}@example.com"
    password = "testpass123"

    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Usuário Estoque",
            "company_id": company_id,
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    return company_id, {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_get_menu_creates_manual_catalog_when_missing(client, db):
    company_id, headers = _auth_headers_for_company(client, db)

    response = client.get("/api/v1/menu", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["catalog"]["name"] == "Cardápio"
    assert payload["catalog"]["source_type"] == "manual"
    assert payload["categories"] == []
    assert payload["items"] == []

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
        .one()
    )
    assert catalog.name == "Cardápio"
    assert catalog.source_type == "manual"


def test_create_category_for_active_catalog(client, db):
    company_id, headers = _auth_headers_for_company(client, db)

    response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={
            "name": "Bebidas",
            "description": "Geladas e quentes",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Bebidas"
    assert payload["description"] == "Geladas e quentes"
    assert payload["items_count"] == 0

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
        .one()
    )
    category = db.query(MenuCategory).filter(MenuCategory.catalog_id == catalog.id).one()
    assert category.name == "Bebidas"


def test_create_and_update_item_with_custom_attributes(client, db):
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Lanches"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    create_response = client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "X-Burger",
            "description": "Pão, carne e queijo",
            "price": "24.90",
            "is_available": True,
            "sku": "XBURGER-001",
            "stock_quantity": 10,
            "custom_attributes": [
                {"key": "tamanho", "value": "grande"},
                {"key": "observacao", "value": "acompanha fritas"},
            ],
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["name"] == "X-Burger"
    assert created_payload["sku"] == "XBURGER-001"
    assert created_payload["stock_quantity"] == 10
    assert created_payload["custom_attributes"] == [
        {"key": "tamanho", "value": "grande"},
        {"key": "observacao", "value": "acompanha fritas"},
    ]

    update_response = client.patch(
        f"/api/v1/menu/items/{created_payload['id']}",
        headers=headers,
        json={
            "description": "Pão, carne, queijo e molho",
            "is_available": False,
            "sku": "XBURGER-002",
            "stock_quantity": 15,
            "custom_attributes": [
                {"key": "tamanho", "value": "família"},
            ],
        },
    )

    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["description"] == "Pão, carne, queijo e molho"
    assert updated_payload["is_available"] is False
    assert updated_payload["sku"] == "XBURGER-002"
    assert updated_payload["stock_quantity"] == 15
    assert updated_payload["custom_attributes"] == [
        {"key": "tamanho", "value": "família"},
    ]

    item = db.query(MenuItem).filter(MenuItem.id == created_payload["id"]).one()
    assert item.is_available is False
    assert item.sku == "XBURGER-002"
    assert item.stock_quantity == 15


def test_editing_imported_catalog_marks_it_manual_and_delete_category_removes_items(client, db):
    company_id, headers = _auth_headers_for_company(client, db)

    catalog = MenuCatalog(
        company_id=company_id,
        name="Cardápio",
        source_type="json",
        source_file="/tmp/menu.json",
        is_active=True,
    )
    db.add(catalog)
    db.flush()
    catalog_id = catalog.id

    category = MenuCategory(catalog_id=catalog.id, name="Pratos", sort_order=1)
    db.add(category)
    db.flush()

    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name="Executivo",
        is_available=True,
        sort_order=1,
    )
    db.add(item)
    db.commit()
    item_id = item.id

    update_response = client.patch(
        f"/api/v1/menu/categories/{category.id}",
        headers=headers,
        json={"description": "Categoria principal"},
    )

    assert update_response.status_code == 200
    persisted_catalog = db.query(MenuCatalog).filter(MenuCatalog.id == catalog_id).one()
    assert persisted_catalog.source_type == "manual"
    assert persisted_catalog.source_file is None

    delete_response = client.delete(
        f"/api/v1/menu/categories/{category.id}",
        headers=headers,
    )

    assert delete_response.status_code == 204
    assert db.query(MenuCategory).filter(MenuCategory.id == category.id).count() == 0
    assert db.query(MenuItem).filter(MenuItem.id == item_id).count() == 0


def test_create_item_with_sku_and_stock(client, db):
    """Test creating item with SKU and stock quantity fields."""
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Bebidas"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    create_response = client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Coca-Cola",
            "description": "Refrigerante 350ml",
            "price": "5.00",
            "is_available": True,
            "sku": "COCA-001",
            "stock_quantity": 50,
        },
    )

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["sku"] == "COCA-001"
    assert payload["stock_quantity"] == 50

    item = db.query(MenuItem).filter(MenuItem.id == payload["id"]).one()
    assert item.sku == "COCA-001"
    assert item.stock_quantity == 50


def test_duplicate_sku_rejected(client, db):
    """Test that duplicate SKUs are rejected."""
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Bebidas"},
    )
    category_id = category_response.json()["id"]

    # Create first item with SKU
    client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Coca-Cola",
            "price": "5.00",
            "sku": "COCA-001",
        },
    )

    # Try to create second item with same SKU
    duplicate_response = client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Pepsi",
            "price": "4.50",
            "sku": "COCA-001",  # Duplicate SKU
        },
    )

    assert duplicate_response.status_code == 409


def test_update_sku_with_uniqueness_validation(client, db):
    """Test that SKU updates respect uniqueness."""
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Bebidas"},
    )
    category_id = category_response.json()["id"]

    # Create two items with different SKUs
    item1_response = client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Coca-Cola",
            "price": "5.00",
            "sku": "COCA-001",
        },
    )
    item1_id = item1_response.json()["id"]

    client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Pepsi",
            "price": "4.50",
            "sku": "PEPSI-001",
        },
    )

    # Try to update item1 with item2's SKU
    update_response = client.patch(
        f"/api/v1/menu/items/{item1_id}",
        headers=headers,
        json={"sku": "PEPSI-001"},  # Already used by item2
    )

    assert update_response.status_code == 409


def test_stock_quantity_validation_on_delete(client, db):
    """Test that items with stock cannot be deleted via category deletion."""
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Lanches"},
    )
    category_id = category_response.json()["id"]

    # Create item with stock
    client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "X-Burger",
            "price": "24.90",
            "stock_quantity": 10,  # Has stock
        },
    )

    # Try to delete category with items that have stock
    delete_response = client.delete(
        f"/api/v1/menu/categories/{category_id}",
        headers=headers,
    )

    # Should fail due to stock validation
    assert delete_response.status_code == 400


def test_list_menu_includes_sku_and_stock(client, db):
    """Test that menu snapshot includes SKU and stock quantity."""
    _, headers = _auth_headers_for_company(client, db)

    category_response = client.post(
        "/api/v1/menu/categories",
        headers=headers,
        json={"name": "Bebidas"},
    )
    category_id = category_response.json()["id"]

    client.post(
        "/api/v1/menu/items",
        headers=headers,
        json={
            "category_id": category_id,
            "name": "Coca-Cola",
            "price": "5.00",
            "sku": "COCA-001",
            "stock_quantity": 50,
        },
    )

    menu_response = client.get("/api/v1/menu", headers=headers)
    assert menu_response.status_code == 200
    payload = menu_response.json()

    assert len(payload["items"]) == 1
    assert payload["items"][0]["sku"] == "COCA-001"
    assert payload["items"][0]["stock_quantity"] == 50


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
