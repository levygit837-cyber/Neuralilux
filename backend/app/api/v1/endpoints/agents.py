from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def list_agents(db: Session = Depends(get_db)):
    """List all AI agents"""
    return {"message": "List agents endpoint - to be implemented"}


@router.post("/")
async def create_agent(db: Session = Depends(get_db)):
    """Create a new AI agent"""
    return {"message": "Create agent endpoint - to be implemented"}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get agent details"""
    return {"message": f"Get agent {agent_id} - to be implemented"}


@router.put("/{agent_id}")
async def update_agent(agent_id: str, db: Session = Depends(get_db)):
    """Update agent configuration"""
    return {"message": f"Update agent {agent_id} - to be implemented"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Delete an agent"""
    return {"message": f"Delete agent {agent_id} - to be implemented"}


@router.post("/{agent_id}/train")
async def train_agent(agent_id: str, db: Session = Depends(get_db)):
    """Train agent with documents"""
    return {"message": f"Train agent {agent_id} - to be implemented"}


@router.post("/{agent_id}/test")
async def test_agent(agent_id: str, db: Session = Depends(get_db)):
    """Test agent with a message"""
    return {"message": f"Test agent {agent_id} - to be implemented"}
