"""Company e o Agent dela: cada usuário vê e edita só a própria Company; o superusuário, todas."""
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.access import get_company_for_user
from app.api.deps import get_current_user, get_db, require_superuser
from app.models import Agent, User
from app.schemas.company import (
    AgentSettings,
    AgentSettingsUpdate,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
)
from app.services.company_service import (
    company_agent,
    create_company,
    delete_company,
    list_companies,
    update_company,
)

logger = structlog.get_logger()
router = APIRouter()

# Só o superusuário muda: o ramo escolhe o Pack do Agent e `is_active` liga/desliga a Company.
_SUPERUSER_ONLY_FIELDS = ("business_type_id", "is_active")


def _agent_for_user(db: Session, company_id: str, user: User) -> Agent:
    get_company_for_user(db, company_id, user)
    agent = company_agent(db, company_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company has no active agent")
    return agent


def _agent_settings(agent: Agent) -> AgentSettings:
    return AgentSettings(
        temperature=agent.temperature, max_tokens=agent.max_tokens or 1000, system_prompt=agent.system_prompt
    )


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Cria uma Company; só o superusuário (o dono comum só edita a que já tem)."""
    try:
        return create_company(db, company)
    except Exception:
        logger.exception("Unexpected error creating company")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating company",
        )


@router.get("/", response_model=List[CompanyResponse])
async def read_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Companies visíveis ao usuário: a dele (ou todas, para o superusuário)."""
    if current_user.is_superuser:
        return list_companies(db, skip=skip, limit=limit)
    if current_user.company_id is None:  # sem Company: nada a listar (`company_id=None` listaria todas)
        return []
    return list_companies(db, skip=skip, limit=limit, company_id=current_user.company_id)


@router.get("/{company_id}", response_model=CompanyResponse)
async def read_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get company by ID"""
    return get_company_for_user(db, company_id, current_user)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_existing_company(
    company_id: str,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atualiza a configuração da Company (só campos enviados); 403 fora da própria Company."""
    get_company_for_user(db, company_id, current_user)
    if not current_user.is_superuser and any(f in company_update.model_fields_set for f in _SUPERUSER_ONLY_FIELDS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a superuser can change this field")
    return update_company(db, company_id, company_update)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_company(
    company_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    """Desativa a Company (soft delete); só o superusuário, como qualquer mudança em `is_active`."""
    if not delete_company(db, company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return None


@router.get("/{company_id}/agent", response_model=AgentSettings)
async def read_company_agent(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ajustes de resposta do Agent da Company."""
    return _agent_settings(_agent_for_user(db, company_id, current_user))


@router.put("/{company_id}/agent", response_model=AgentSettings)
async def update_company_agent(
    company_id: str,
    update: AgentSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atualiza temperatura, limite de tokens e instruções do Agent (só campos enviados); o modelo vem do Gateway."""
    agent = _agent_for_user(db, company_id, current_user)
    for field in update.model_fields_set:
        setattr(agent, field, getattr(update, field))
    db.commit()
    db.refresh(agent)
    return _agent_settings(agent)
