from app.models.models import Company, MenuCatalog, MenuCategory, MenuItem


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
            "custom_attributes": [
                {"key": "tamanho", "value": "grande"},
                {"key": "observacao", "value": "acompanha fritas"},
            ],
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["name"] == "X-Burger"
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
            "custom_attributes": [
                {"key": "tamanho", "value": "família"},
            ],
        },
    )

    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["description"] == "Pão, carne, queijo e molho"
    assert updated_payload["is_available"] is False
    assert updated_payload["custom_attributes"] == [
        {"key": "tamanho", "value": "família"},
    ]

    item = db.query(MenuItem).filter(MenuItem.id == created_payload["id"]).one()
    assert item.is_available is False


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
