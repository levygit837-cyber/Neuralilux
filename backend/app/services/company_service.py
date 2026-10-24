from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import commit_or_rollback
from app.models import Agent, Company
from app.schemas.company import CompanyCreate, CompanyUpdate


def create_company(db: Session, company: CompanyCreate) -> Company:
    """Create a new company"""
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


def get_company(db: Session, company_id: str) -> Optional[Company]:
    """Get company by ID"""
    return db.query(Company).filter(Company.id == company_id).first()


def list_companies(db: Session, skip: int = 0, limit: int = 100, company_id: Optional[str] = None) -> List[Company]:
    """Companies ativas com paginação; `company_id` restringe a uma Company (sem ele, todas)."""
    query = db.query(Company).filter(Company.is_active == True)  # noqa: E712
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    return query.order_by(Company.name, Company.id).offset(skip).limit(limit).all()


def update_company(db: Session, company_id: str, company_update: CompanyUpdate) -> Optional[Company]:
    """Update company"""
    db_company = get_company(db, company_id)
    if not db_company:
        return None

    update_data = company_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_company, key, value)

    db.commit()
    db.refresh(db_company)
    return db_company


def delete_company(db: Session, company_id: str) -> bool:
    """Soft delete company (set is_active to False)"""
    db_company = get_company(db, company_id)
    if not db_company:
        return False

    db_company.is_active = False
    db.commit()
    return True


def company_agent(db: Session, company_id: Optional[str]) -> Optional[Agent]:
    """O Agent ativo mais antigo da Company. Só lê; o Turn usa `agent_service.resolve_turn_agent`."""
    if not company_id:
        return None
    return (
        db.query(Agent)
        .filter(Agent.company_id == company_id, Agent.is_active == True)  # noqa: E712
        .order_by(Agent.created_at, Agent.id)
        .first()
    )


def update_agent_settings(db: Session, agent: Agent, fields: dict) -> Agent:
    """Grava os ajustes do Agent e comita (uma operação, um commit); em erro de commit desfaz e relança."""
    for name, value in fields.items():
        setattr(agent, name, value)
    commit_or_rollback(db)
    db.refresh(agent)
    return agent
