#!/usr/bin/env python3
"""
Seed data script for Neuralilux
Creates initial data including business types, product types, test company and test user
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models.models import BusinessType, ProductType, Company, User
from app.core.security import get_password_hash
from app.services.menu_catalog_service import sync_macedos_menu_from_json


def create_business_types(db: Session):
    """Create default business types"""
    business_types = [
        {
            "name": "Restaurante",
            "slug": "restaurant",
            "description": "Estabelecimentos de alimentação e gastronomia",
            "icon": "restaurant"
        },
        {
            "name": "Clínica",
            "slug": "clinic",
            "description": "Clínicas médicas e de saúde",
            "icon": "medical_services"
        },
        {
            "name": "Loja",
            "slug": "store",
            "description": "Lojas de varejo e comércio",
            "icon": "store"
        },
        {
            "name": "Serviços",
            "slug": "services",
            "description": "Prestadores de serviços diversos",
            "icon": "build"
        }
    ]

    created = []
    for bt_data in business_types:
        # Check if already exists
        existing = db.query(BusinessType).filter(BusinessType.slug == bt_data["slug"]).first()
        if not existing:
            bt = BusinessType(**bt_data)
            db.add(bt)
            created.append(bt_data["name"])

    db.commit()
    return created


def create_product_types(db: Session):
    """Create default product types"""
    product_types = [
        {
            "name": "Comida",
            "slug": "food",
            "description": "Alimentos e pratos",
            "icon": "restaurant_menu"
        },
        {
            "name": "Bebida",
            "slug": "beverage",
            "description": "Bebidas em geral",
            "icon": "local_bar"
        },
        {
            "name": "Serviço",
            "slug": "service",
            "description": "Serviços prestados",
            "icon": "room_service"
        },
        {
            "name": "Produto Físico",
            "slug": "physical_product",
            "description": "Produtos físicos para venda",
            "icon": "inventory_2"
        }
    ]

    created = []
    for pt_data in product_types:
        # Check if already exists
        existing = db.query(ProductType).filter(ProductType.slug == pt_data["slug"]).first()
        if not existing:
            pt = ProductType(**pt_data)
            db.add(pt)
            created.append(pt_data["name"])

    db.commit()
    return created


def create_test_company(db: Session):
    """Create test company"""
    # Get restaurant business type
    restaurant_type = db.query(BusinessType).filter(BusinessType.slug == "restaurant").first()
    if not restaurant_type:
        print("Error: Restaurant business type not found")
        return None

    # Check if test company already exists
    existing = db.query(Company).filter(Company.name == "Empresa Teste").first()
    if existing:
        print("Test company already exists")
        return existing

    # Create test company
    company = Company(
        name="Empresa Teste",
        business_type_id=restaurant_type.id,
        description="Empresa de teste para desenvolvimento",
        address_street="Rua Teste",
        address_number="123",
        address_city="São Paulo",
        address_state="SP",
        address_zip="01234-567",
        phone="(11) 98765-4321",
        email="contato@empresateste.com",
        whatsapp="5511987654321",
        business_hours={
            "monday": {"open": "08:00", "close": "18:00", "closed": False},
            "tuesday": {"open": "08:00", "close": "18:00", "closed": False},
            "wednesday": {"open": "08:00", "close": "18:00", "closed": False},
            "thursday": {"open": "08:00", "close": "18:00", "closed": False},
            "friday": {"open": "08:00", "close": "18:00", "closed": False},
            "saturday": {"open": "09:00", "close": "14:00", "closed": False},
            "sunday": {"open": "00:00", "close": "00:00", "closed": True}
        },
        ai_system_prompt="Você é um assistente virtual da Empresa Teste. Seja educado e prestativo.",
        ai_model="gpt-4-turbo-preview",
        ai_temperature=70,
        ai_max_tokens=1000
    )

    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_or_update_test_user(db: Session, company_id: str):
    """Ensure the default test user points to the target company with the expected password."""
    existing = db.query(User).filter(User.email == "usuario@teste.com").first()
    if existing:
        existing.full_name = "Usuário Teste"
        existing.company_id = company_id
        existing.hashed_password = get_password_hash("teste123")
        existing.is_active = True
        existing.is_superuser = False
        db.commit()
        db.refresh(existing)
        print("Test user updated")
        return existing

    user = User(
        email="usuario@teste.com",
        hashed_password=get_password_hash("teste123"),
        full_name="Usuário Teste",
        company_id=company_id,
        is_active=True,
        is_superuser=False
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main():
    """Main function to seed database"""
    print("Starting database seed...")

    # Create tables if they don't exist
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    # Create session
    db = SessionLocal()

    try:
        # Create business types
        print("\nCreating business types...")
        business_types = create_business_types(db)
        if business_types:
            print(f"Created: {', '.join(business_types)}")
        else:
            print("All business types already exist")

        # Create product types
        print("\nCreating product types...")
        product_types = create_product_types(db)
        if product_types:
            print(f"Created: {', '.join(product_types)}")
        else:
            print("All product types already exist")

        # Create test company
        print("\nCreating test company...")
        company = create_test_company(db)
        if company:
            print(f"Created company: {company.name} (ID: {company.id})")

        print("\nImporting Macedos menu...")
        catalog = sync_macedos_menu_from_json(db)
        print(f"Imported catalog: {catalog.name}")

        print("\nEnsuring test user is bound to Macedos...")
        user = create_or_update_test_user(db, catalog.company_id)
        if user:
            target_company = db.query(Company).filter(Company.id == catalog.company_id).first()
            print(f"User ready: {user.email}")
            print(f"  Name: {user.full_name}")
            print(f"  Password: teste123")
            print(f"  Company: {target_company.name if target_company else catalog.company_id}")

        print("\n✅ Database seed completed successfully!")

    except Exception as e:
        print(f"\n❌ Error seeding database: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
