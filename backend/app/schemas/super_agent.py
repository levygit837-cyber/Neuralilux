"""
Super Agent Schemas - Pydantic models for Super Agent API.
Defines request/response schemas for the Super Agent (Business Assistant) endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============== Enums ==============


class SuperAgentRoleEnum(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class SuperAgentIntentEnum(str, Enum):
    DATABASE_QUERY = "database_query"
    WHATSAPP_ACTION = "whatsapp_action"
    DOCUMENT_CREATION = "document_creation"
    ANALYSIS = "analysis"
    KNOWLEDGE_STORE = "knowledge_store"
    GENERAL = "general"


# ============== Session Schemas ==============


class SuperAgentSessionCreate(BaseModel):
    """Create a new Super Agent session."""
    title: Optional[str] = Field(None, max_length=200, description="Optional session title")


class SuperAgentSessionResponse(BaseModel):
    """Response schema for a Super Agent session."""
    id: str
    company_id: str
    user_id: str
    title: Optional[str] = None
    is_active: bool
    interaction_count: int
    last_checkpoint_at: int
    last_message_preview: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuperAgentSessionList(BaseModel):
    """List of Super Agent sessions."""
    items: List[SuperAgentSessionResponse]
    total: int


# ============== Message Schemas ==============


class SuperAgentMessageSend(BaseModel):
    """Send a message to the Super Agent."""
    message: str = Field(..., min_length=1, max_length=10000, description="User message to the agent")


class SuperAgentMessageResponse(BaseModel):
    """Response schema for a Super Agent message."""
    id: str
    session_id: str
    role: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    thinking_content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SuperAgentMessageList(BaseModel):
    """List of Super Agent messages."""
    items: List[SuperAgentMessageResponse]
    total: int


class ToolCallResponse(BaseModel):
    """Structured tool call metadata returned by chat endpoints."""
    name: str
    input: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    status: str = "completed"
    trace_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class SuperAgentChatResponse(BaseModel):
    """Response after sending a message to the Super Agent."""
    session_id: str
    message_id: str
    response: str
    thinking: Optional[str] = None
    intent: Optional[str] = None
    tool_used: Optional[str] = None
    tool_calls: Optional[List[ToolCallResponse]] = None
    interaction_count: int
    checkpoint_created: bool = False


# ============== Checkpoint Schemas ==============


class SuperAgentCheckpointResponse(BaseModel):
    """Response schema for a Super Agent checkpoint."""
    id: str
    session_id: str
    interaction_number: int
    summary: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SuperAgentCheckpointList(BaseModel):
    """List of Super Agent checkpoints."""
    items: List[SuperAgentCheckpointResponse]
    total: int


# ============== Knowledge Schemas ==============


class SuperAgentKnowledgeStore(BaseModel):
    """Store knowledge in the Super Agent knowledge base."""
    category: str = Field(..., min_length=1, max_length=100, description="Knowledge category")
    key: str = Field(..., min_length=1, max_length=200, description="Knowledge key")
    value: str = Field(..., min_length=1, description="Knowledge content")


class SuperAgentKnowledgeResponse(BaseModel):
    """Response schema for a Super Agent knowledge item."""
    id: str
    company_id: str
    category: str
    key: str
    value: str
    source_session_id: Optional[str] = None
    confidence: int
    access_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuperAgentKnowledgeSearch(BaseModel):
    """Search the knowledge base."""
    category: Optional[str] = Field(None, description="Filter by category")
    query: str = Field(..., min_length=1, description="Search query (text match)")


class SuperAgentKnowledgeList(BaseModel):
    """List of knowledge items."""
    items: List[SuperAgentKnowledgeResponse]
    total: int


# ============== Document Schemas ==============


class SuperAgentDocumentResponse(BaseModel):
    """Response schema for a Super Agent document."""
    id: str
    session_id: str
    company_id: str
    filename: str
    file_type: str
    content: Optional[str] = None
    content_base64: Optional[str] = None
    file_size: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SuperAgentDocumentList(BaseModel):
    """List of Super Agent documents."""
    items: List[SuperAgentDocumentResponse]
    total: int
