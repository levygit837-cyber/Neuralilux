from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services.inference_service import get_inference_service
from app.schemas.conversations import (
    InferenceRequest, InferenceResponse,
    InferenceChatRequest, InferenceChatResponse
)

logger = structlog.get_logger()
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


@router.post("/inference", response_model=InferenceResponse)
async def message_inference(
    data: InferenceRequest,
    current_user=Depends(get_current_user)
):
    """
    Generate AI response for messages using LM Studio.
    
    This endpoint sends messages to a local LM Studio instance
    and returns the generated response from the AI model.
    
    Args:
        data: Inference request with messages and optional parameters
        
    Returns:
        InferenceResponse with the generated content and metadata
    """
    try:
        logger.info("Processing inference request", message_count=len(data.messages))
        
        inference_service = get_inference_service()
        result = await inference_service.chat_completion(
            messages=data.messages,
            system_prompt=data.system_prompt,
            max_tokens=data.max_tokens,
            temperature=data.temperature
        )
        
        return InferenceResponse(**result)
        
    except Exception as e:
        logger.error("Error in message inference endpoint", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing inference: {str(e)}"
        )


@router.post("/inference/chat", response_model=InferenceChatResponse)
async def inference_chat(
    data: InferenceChatRequest,
    current_user=Depends(get_current_user)
):
    """
    Simple chat inference endpoint.
    
    Accepts a single message and optional conversation history,
    returns the AI-generated response.
    
    Args:
        data: Chat inference request with message and optional history
        
    Returns:
        InferenceChatResponse with the generated response
    """
    try:
        inference_service = get_inference_service()
        response = await inference_service.generate_response(
            user_message=data.message,
            conversation_history=data.conversation_history,
            system_prompt=data.system_prompt
        )
        
        return InferenceChatResponse(
            response=response,
            model=inference_service.model
        )
        
    except Exception as e:
        logger.error("Error in inference chat endpoint", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


@router.get("/inference/health")
async def inference_health_check():
    """
    Check LM Studio availability and health status.
    
    Returns:
        Health status of the LM Studio connection
    """
    try:
        inference_service = get_inference_service()
        is_healthy = await inference_service.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "url": inference_service.base_url,
            "model": inference_service.model,
            "max_tokens": inference_service.max_tokens,
            "temperature": inference_service.temperature
        }
    except Exception as e:
        logger.error("Error checking LM Studio health", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }
