from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.deps import get_db
from app.models import Agent, User
from app.services.agent_service import agents_for_user

router = APIRouter()


class AgentListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class AgentListResponse(BaseModel):
    items: list[AgentListItem]
    total: int


@router.get("/", response_model=AgentListResponse)
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agents ativos da Company do usuário (todos, para o superusuário)."""
    agents = agents_for_user(db, current_user).order_by(Agent.name.asc()).all()

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
