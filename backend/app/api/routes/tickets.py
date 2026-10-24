"""
Tickets API - leitura dos Tickets de Handoff.

Assumir e devolver a Conversation são transições do `handoff_service`, expostas só pelas rotas de controle
humano da Conversation (`take-control` / `release-control`). Aqui não há mutação de Ticket.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import Ticket, User
from app.schemas.ticket import TicketListResponse, TicketResponse

router = APIRouter()


def _scoped_tickets(db: Session, user: User):
    """Query de Tickets limitada às Instances do usuário (superusuário: todas)."""
    query = db.query(Ticket)
    instance_ids = instance_ids_for_user(db, user)
    if instance_ids is not None:
        query = query.filter(Ticket.instance_id.in_(instance_ids))
    return query


@router.get("/", response_model=TicketListResponse)
def list_tickets(
    status: Optional[str] = Query(None, description="Filtrar por status (open, in_progress, closed, expired)"),
    agent_type: Optional[str] = Query(None, description="Filtrar por tipo de agente (sales, sac)"),
    assigned_to: Optional[str] = Query(None, description="Filtrar por atendente atribuído"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista os Tickets das Instances do usuário (superusuário: todos) com filtros opcionais."""
    query = _scoped_tickets(db, current_user)
    if status:
        query = query.filter(Ticket.status == status)
    if agent_type:
        query = query.filter(Ticket.agent_type == agent_type)
    if assigned_to:
        query = query.filter(Ticket.assigned_to == assigned_to)
    query = query.order_by(Ticket.created_at.desc())
    return TicketListResponse(
        tickets=query.offset(skip).limit(limit).all(), total=query.count(), skip=skip, limit=limit
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalhe de um Ticket; fora do escopo do usuário responde 404 (não revela que existe)."""
    ticket = _scoped_tickets(db, current_user).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return ticket
