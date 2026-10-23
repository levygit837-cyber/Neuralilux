"""Contacts - lista de Contacts das Instances do usuário."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
import structlog

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import User, Contact
from app.schemas.contact import ContactResponse, PaginatedContacts

logger = structlog.get_logger()

router = APIRouter()


@router.get("/contacts", response_model=PaginatedContacts)
async def list_contacts(
    instance_id: Optional[str] = Query(None, description="Filter by instance ID"),
    is_blocked: Optional[bool] = Query(None, description="Filter blocked contacts"),
    is_business: Optional[bool] = Query(None, description="Filter business contacts"),
    search: Optional[str] = Query(None, description="Search by name or phone number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List contacts with optional filters.

    - **instance_id**: Filter by WhatsApp instance.
    - **is_blocked**: Filter blocked/unblocked contacts.
    - **is_business**: Filter business/regular contacts.
    - **search**: Search by name, push_name or phone number.
    """
    query = db.query(Contact)

    # Filter by instances the user owns (unless superuser)
    user_instance_ids = instance_ids_for_user(db, current_user)
    if user_instance_ids is not None:
        query = query.filter(Contact.instance_id.in_(user_instance_ids))

    if instance_id:
        query = query.filter(Contact.instance_id == instance_id)

    if is_blocked is not None:
        query = query.filter(Contact.is_blocked == is_blocked)

    if is_business is not None:
        query = query.filter(Contact.is_business == is_business)

    if search:
        query = query.filter(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.phone_number.ilike(f"%{search}%"),
                Contact.push_name.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    contacts = (
        query.order_by(Contact.name.asc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return PaginatedContacts(
        items=[ContactResponse.model_validate(c) for c in contacts],
        total=total,
        skip=skip,
        limit=limit,
    )
