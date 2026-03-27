"""
Schemas for inference/conversation endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class MessageItem(BaseModel):
    """Single message in conversation."""
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class InferenceRequest(BaseModel):
    """Request schema for /messages/inference endpoint."""
    messages: List[MessageItem] = Field(
        ..., 
        min_length=1, 
        description="List of conversation messages"
    )
    system_prompt: Optional[str] = Field(
        None, 
        description="Optional system prompt to guide the model"
    )
    max_tokens: Optional[int] = Field(
        1024, 
        ge=1, 
        le=4096, 
        description="Maximum tokens in response"
    )
    temperature: Optional[float] = Field(
        0.7, 
        ge=0.0, 
        le=2.0, 
        description="Sampling temperature"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Olá, como você pode me ajudar?"}
                ],
                "system_prompt": "Você é um assistente prestativo.",
                "max_tokens": 512,
                "temperature": 0.7
            }
        }


class InferenceResponse(BaseModel):
    """Response schema for /messages/inference endpoint."""
    content: str = Field(..., description="Generated response content")
    model: str = Field(..., description="Model used for generation")
    usage: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Token usage statistics"
    )
    finish_reason: Optional[str] = Field(
        None, 
        description="Reason for completion"
    )


class InferenceChatRequest(BaseModel):
    """Request schema for /messages/inference/chat endpoint."""
    message: str = Field(
        ..., 
        min_length=1, 
        description="User message"
    )
    conversation_history: Optional[List[MessageItem]] = Field(
        None, 
        description="Optional previous conversation history"
    )
    system_prompt: Optional[str] = Field(
        None, 
        description="Optional system prompt"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Qual é a capital do Brasil?",
                "conversation_history": [],
                "system_prompt": "Responda em português."
            }
        }


class InferenceChatResponse(BaseModel):
    """Response schema for /messages/inference/chat endpoint."""
    response: str = Field(..., description="AI-generated response")
    model: str = Field(..., description="Model used for generation")
