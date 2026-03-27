from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.services.message_queue_service import message_queue_service

router = APIRouter()


class SendMessageRequest(BaseModel):
    """Schema for sending a WhatsApp message"""
    instance_name: str
    to: str
    text: str
    quoted_message_id: Optional[str] = None


class MessageResponse(BaseModel):
    """Schema for message response"""
    status: str
    message: str
    queued: bool = False


@router.get("/")
async def list_messages(db: Session = Depends(get_db)):
    """List messages with filters"""
    return {"message": "List messages endpoint - to be implemented"}


@router.post("/send", response_model=MessageResponse)
async def send_message(request: SendMessageRequest, db: Session = Depends(get_db)):
    """
    Send a message via WhatsApp
    
    The message will be queued in RabbitMQ for async processing.
    """
    try:
        message_data = {
            "instance_name": request.instance_name,
            "to": request.to,
            "text": request.text,
            "quoted_message_id": request.quoted_message_id,
        }
        
        # Publish to RabbitMQ for async processing
        queued = message_queue_service.publish_outgoing_message(message_data)
        
        if not queued:
            raise HTTPException(
                status_code=500,
                detail="Failed to queue message for sending"
            )
        
        return MessageResponse(
            status="success",
            message="Message queued for sending",
            queued=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{message_id}")
async def get_message(message_id: str, db: Session = Depends(get_db)):
    """Get message details"""
    return {"message": f"Get message {message_id} - to be implemented"}


@router.get("/conversation/{phone_number}")
async def get_conversation(phone_number: str, db: Session = Depends(get_db)):
    """Get conversation history with a contact"""
    return {"message": f"Get conversation with {phone_number} - to be implemented"}


@router.get("/queue/stats")
async def get_queue_stats():
    """Get message queue statistics"""
    try:
        stats = {
            "incoming": message_queue_service.get_queue_stats("whatsapp.messages.incoming"),
            "outgoing": message_queue_service.get_queue_stats("whatsapp.messages.send"),
            "ai_processing": message_queue_service.get_queue_stats("ai.processing"),
            "webhooks": message_queue_service.get_queue_stats("webhooks.evolution"),
        }
        return {"status": "success", "queues": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))