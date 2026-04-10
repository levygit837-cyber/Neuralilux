from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.models import Company
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


def list_companies(db: Session, skip: int = 0, limit: int = 100) -> List[Company]:
    """List all companies with pagination"""
    return db.query(Company).filter(Company.is_active == True).offset(skip).limit(limit).all()


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
