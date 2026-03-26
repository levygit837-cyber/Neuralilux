from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.services.company_service import (
    create_company,
    get_company,
    list_companies,
    update_company,
    delete_company
)
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new company"""
    try:
        db_company = create_company(db, company)
        return db_company
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating company: {str(e)}"
        )


@router.get("/", response_model=List[CompanyResponse])
async def read_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all companies"""
    companies = list_companies(db, skip=skip, limit=limit)
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
async def read_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get company by ID"""
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_existing_company(
    company_id: str,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update company"""
    company = update_company(db, company_id, company_update)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete company (soft delete)"""
    success = delete_company(db, company_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return None
