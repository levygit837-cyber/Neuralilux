#!/usr/bin/env python3
"""
Seed data script for Neuralilux
Creates initial data including business types, test company and test user
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models import Agent, BusinessType, Company, Instance, User, DeliveryZone
from app.core.security import get_password_hash
from app.services.menu.sync import sync_menu_from_json
from app.llm.registry import ensure_default_gateway


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
    )

    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _dev_superuser() -> bool:
    """`SEED_DEV_SUPERUSER=1` promove o usuario de dev a superuser (necessario para editar Gateways)."""
    return os.environ.get("SEED_DEV_SUPERUSER") == "1"


def create_or_update_test_user(db: Session, company_id: str):
    """Ensure the default test user points to the target company with the expected password."""
    existing = db.query(User).filter(User.email == "usuario@teste.com").first()
    if existing:
        existing.full_name = "Usuário Teste"
        existing.company_id = company_id
        existing.hashed_password = get_password_hash("teste123")
        existing.is_active = True
        existing.is_superuser = _dev_superuser()
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
        is_superuser=_dev_superuser()
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_company_agents(db: Session):
    """Um Agent por Company, ligado às Instances da Company que ainda não têm Agent (idempotente).

    Instance ligada aqui sai com `agent_enabled=True`, para que um seed novo já responda. Quem já tinha Agent
    não é tocado: reexecutar o seed nunca religa uma Instance que o operador desligou.

    O comportamento vem do núcleo e do Pack do Business Type; `system_prompt` (instruções da Company) fica vazio
    até a Company escrever as dela no painel. Instance sem Company e Instance já ligada a outro Agent ficam como estão.
    """
    created = []
    for company in db.query(Company).order_by(Company.name).all():
        agent = db.query(Agent).filter(Agent.company_id == company.id).order_by(Agent.created_at).first()
        if agent is None:
            owner = db.query(User).filter(User.company_id == company.id).order_by(User.email).first()
            agent = Agent(
                name=f"Atendente {company.name}",
                description=f"Agent de atendimento de {company.name}",
                company_id=company.id,
                owner_id=owner.id if owner else None,
                is_active=True,
            )
            db.add(agent)
            db.flush()
            created.append(company.name)
        db.query(Instance).filter(
            Instance.company_id == company.id, Instance.agent_id.is_(None)
        ).update({Instance.agent_id: agent.id, Instance.agent_enabled: True}, synchronize_session="fetch")
    db.commit()
    return created


SAMPLE_MENU_PATH = Path(__file__).resolve().with_name("sample_menu.json")

SAMPLE_BUSINESS_HOURS = {
    "mon": [["11:00", "22:00"]],
    "tue": [["11:00", "22:00"]],
    "wed": [["11:00", "22:00"]],
    "thu": [["11:00", "22:00"]],
    "fri": [["11:00", "23:00"]],
    "sat": [["11:00", "23:00"]],
    "sun": [["11:00", "22:00"]],
}


def configure_company_operations(db: Session, company: Company):
    """Horários, pedido mínimo e uma zona de entrega de exemplo para a Company (idempotente)."""
    if not company.business_hours:
        company.business_hours = SAMPLE_BUSINESS_HOURS
    if company.minimum_order is None:
        company.minimum_order = 30.00

    created = []
    if db.query(DeliveryZone).filter(DeliveryZone.company_id == company.id).count() == 0:
        zone = DeliveryZone(
            company_id=company.id,
            name="Centro",
            neighborhoods=["Centro", "Centro Histórico"],
            delivery_fee=5.00,
            minimum_order_value=0,
        )
        db.add(zone)
        created.append(zone.name)
    db.commit()
    return created


def main():
    """Main function to seed database"""
    print("Starting database seed...")

    # O schema vem exclusivamente do Alembic (alembic upgrade head)

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

        print("\nCreating test company...")
        company = create_test_company(db)
        if company is None:
            raise RuntimeError("Business type 'restaurant' not found")
        print(f"Test company: {company.name} (ID: {company.id})")

        print("\nImporting sample menu...")
        catalog = sync_menu_from_json(db, company, SAMPLE_MENU_PATH)
        print(f"Imported catalog: {catalog.name}")

        print("\nConfiguring company operations (hours, minimum order, delivery zone)...")
        zones = configure_company_operations(db, company)
        print(f"Created zones: {', '.join(zones)}" if zones else "Delivery zones already exist")

        print("\nEnsuring test user is bound to the test company...")
        user = create_or_update_test_user(db, company.id)
        if user:
            print(f"User ready: {user.email}")
            print(f"  Name: {user.full_name}")
            print(f"  Password: teste123")
            print(f"  Company: {company.name}")

        print("\nCreating one Agent per company and binding the company's instances...")
        agents = create_company_agents(db)
        print(f"Created agents for: {', '.join(agents)}" if agents else "All companies already have an Agent")

        print("\nRegistering default inference gateway (Kiro-backend)...")
        gateway = ensure_default_gateway(db)
        print("Gateway created: Kiro-backend (Sonnet 5.5, effort low)" if gateway else "Gateway already exists")

        print("\n✅ Database seed completed successfully!")

    except Exception as e:
        print(f"\n❌ Error seeding database: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
