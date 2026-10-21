"""
Tickets API - Endpoints para gerenciar tickets de chamados para humanos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.models import Instance, Ticket, User
from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db

router = APIRouter()


def _scoped_tickets(db: Session, user: User):
    """Query de Tickets limitada às Instances do usuário (superusuário: todas)."""
    query = db.query(Ticket)
    instance_ids = instance_ids_for_user(db, user)
    if instance_ids is not None:
        query = query.filter(Ticket.instance_id.in_(instance_ids))
    return query


def _get_ticket_for_user(db: Session, ticket_id: str, user: User) -> Ticket:
    """Ticket dentro do escopo do usuário; fora dele responde 404 (não revela que existe)."""
    ticket = _scoped_tickets(db, user).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return ticket


def _check_assignee(db: Session, ticket: Ticket, assignee_id: str, current_user: User) -> User:
    """O atendente tem de existir e ser da Company da Instance do Ticket (superusuário atribui a qualquer um)."""
    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not current_user.is_superuser:
        instance = db.query(Instance).filter(Instance.id == ticket.instance_id).first()
        if not instance or not instance.company_id or assignee.company_id != instance.company_id:
            raise HTTPException(
                status_code=403,
                detail="O atendente precisa ser da mesma Company da Instance do Ticket",
            )
    return assignee


@router.get("/")
def list_tickets(
    status: Optional[str] = Query(None, description="Filtrar por status (open, in_progress, closed)"),
    agent_type: Optional[str] = Query(None, description="Filtrar por tipo de agente (sales, sac)"),
    assigned_to: Optional[str] = Query(None, description="Filtrar por atendente atribuído"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista os tickets das Instances do usuário (superusuário: todos) com filtros opcionais.
    """
    query = _scoped_tickets(db, current_user)
    
    if status:
        query = query.filter(Ticket.status == status)
    
    if agent_type:
        query = query.filter(Ticket.agent_type == agent_type)
    
    if assigned_to:
        query = query.filter(Ticket.assigned_to == assigned_to)
    
    # Ordenar por data de criação (mais recentes primeiro)
    query = query.order_by(Ticket.created_at.desc())
    
    tickets = query.offset(skip).limit(limit).all()
    
    total = query.count()
    
    return {
        "tickets": [
            {
                "id": ticket.id,
                "conversation_id": ticket.conversation_id,
                "instance_id": ticket.instance_id,
                "contact_id": ticket.contact_id,
                "agent_type": ticket.agent_type,
                "reason": ticket.reason,
                "content": ticket.content,
                "status": ticket.status,
                "assigned_to": ticket.assigned_to,
                "created_at": ticket.created_at.isoformat(),
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
            }
            for ticket in tickets
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna detalhes de um ticket específico.
    """
    ticket = _get_ticket_for_user(db, ticket_id, current_user)
    
    return {
        "id": ticket.id,
        "conversation_id": ticket.conversation_id,
        "instance_id": ticket.instance_id,
        "contact_id": ticket.contact_id,
        "agent_type": ticket.agent_type,
        "reason": ticket.reason,
        "content": ticket.content,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
    }


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: str,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Atualiza status ou atribuição de um ticket.
    """
    ticket = _get_ticket_for_user(db, ticket_id, current_user)
    
    if status:
        valid_statuses = ["open", "in_progress", "closed"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Status inválido. Valores válidos: {valid_statuses}")
        ticket.status = status
    
    if assigned_to:
        _check_assignee(db, ticket, assigned_to, current_user)
        ticket.assigned_to = assigned_to
    
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    
    return {
        "id": ticket.id,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "updated_at": ticket.updated_at.isoformat()
    }


@router.post("/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Atribui um ticket a um atendente humano.
    """
    ticket = _get_ticket_for_user(db, ticket_id, current_user)
    
    _check_assignee(db, ticket, user_id, current_user)

    ticket.assigned_to = user_id
    ticket.status = "in_progress"
    ticket.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ticket)
    
    return {
        "id": ticket.id,
        "assigned_to": ticket.assigned_to,
        "status": ticket.status,
        "updated_at": ticket.updated_at.isoformat()
    }
