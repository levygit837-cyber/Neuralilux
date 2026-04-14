"""
Tickets API - Endpoints para gerenciar tickets de chamados para humanos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.models import Ticket, User
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    Lista todos os tickets com filtros opcionais.
    """
    query = db.query(Ticket)
    
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
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    
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
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    
    if status:
        valid_statuses = ["open", "in_progress", "closed"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Status inválido. Valores válidos: {valid_statuses}")
        ticket.status = status
    
    if assigned_to:
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
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    
    # Verificar se o usuário existe
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
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
