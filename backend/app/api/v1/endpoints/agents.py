from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models import Agent, User

router = APIRouter()


class AgentListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class AgentListResponse(BaseModel):
    items: list[AgentListItem]
    total: int


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active WhatsApp agents available to the current user."""
    query = db.query(Agent).filter(Agent.is_active == True)

    if not current_user.is_superuser:
        query = query.filter((Agent.owner_id == current_user.id) | (Agent.owner_id.is_(None)))

    agents = query.order_by(Agent.name.asc()).all()

    return AgentListResponse(
        items=[
            AgentListItem(
                id=agent.id,
                name=agent.name,
                description=agent.description,
            )
            for agent in agents
        ],
        total=len(agents),
    )
