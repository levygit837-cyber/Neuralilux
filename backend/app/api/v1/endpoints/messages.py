from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def list_messages(db: Session = Depends(get_db)):
    """List messages with filters"""
    return {"message": "List messages endpoint - to be implemented"}


@router.post("/send")
async def send_message(db: Session = Depends(get_db)):
    """Send a message via WhatsApp"""
    return {"message": "Send message endpoint - to be implemented"}


@router.get("/{message_id}")
async def get_message(message_id: str, db: Session = Depends(get_db)):
    """Get message details"""
    return {"message": f"Get message {message_id} - to be implemented"}


@router.get("/conversation/{phone_number}")
async def get_conversation(phone_number: str, db: Session = Depends(get_db)):
    """Get conversation history with a contact"""
    return {"message": f"Get conversation with {phone_number} - to be implemented"}
