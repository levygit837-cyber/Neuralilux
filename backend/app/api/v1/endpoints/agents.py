from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import uuid

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.models import Agent, User
from app.schemas.super_agent import (
    SuperAgentSessionCreate,
    SuperAgentSessionResponse,
    SuperAgentSessionList,
    SuperAgentMessageSend,
    SuperAgentMessageResponse,
    SuperAgentMessageList,
    SuperAgentChatResponse,
    SuperAgentCheckpointList,
    SuperAgentKnowledgeStore,
    SuperAgentKnowledgeSearch,
    SuperAgentKnowledgeList,
    SuperAgentDocumentList,
    ToolCallResponse,
)
from app.super_agents.context_resolver import resolve_agent_chat_actor

router = APIRouter()


class AgentChatRequest(BaseModel):
    message: str
    company_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class AgentChatSessionRequest(BaseModel):
    company_id: Optional[str] = None
    user_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    message_id: str
    response: str
    thinking: Optional[str] = None
    intent: Optional[str] = None
    tool_calls: Optional[list[ToolCallResponse]] = None
    session_id: str


class AgentChatSessionResponse(BaseModel):
    session_id: str


class AgentListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class AgentListResponse(BaseModel):
    items: list[AgentListItem]
    total: int


def _serialize_super_agent_message(message: dict) -> SuperAgentMessageResponse:
    return SuperAgentMessageResponse(
        id=message["id"],
        session_id=message.get("session_id") or "",
        role=message["role"],
        content=message.get("content"),
        tool_name=message.get("tool_name"),
        tool_input=message.get("tool_input"),
        tool_output=message.get("tool_output"),
        thinking_content=message.get("thinking_content"),
        metadata=message.get("metadata") or message.get("extra_data"),
        created_at=message["created_at"],
    )


async def _create_agent_session(
    db: Session,
    company_id: str,
    user_id: str,
    title: str = "Nova conversa",
) -> str:
    from app.super_agents.memory.session_memory import SessionMemory

    session_id = await SessionMemory.create_session(
        db=db,
        company_id=company_id,
        user_id=user_id,
        title=title,
    )

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return session_id


async def _get_authorized_session(
    db: Session,
    session_id: str,
    current_user: User,
) -> dict:
    from app.super_agents.memory.session_memory import SessionMemory

    session_info = await SessionMemory.get_session(db=db, session_id=session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.is_superuser:
        return session_info

    same_user = str(session_info.get("user_id")) == str(current_user.id)
    same_company = (
        current_user.company_id is not None
        and str(session_info.get("company_id")) == str(current_user.company_id)
    )

    if not same_user and not same_company:
        raise HTTPException(status_code=403, detail="Session does not belong to the current user")

    return session_info


# ============== Super Agent Endpoints ==============


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


@router.post("/super-agent/sessions", response_model=SuperAgentSessionResponse)
async def create_super_agent_session(
    body: SuperAgentSessionCreate,
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
):
    """Create a new Super Agent session."""
    from app.super_agents.agent_executor import super_agent_executor

    session_id = await super_agent_executor.create_session(
        company_id=company_id,
        user_id=user_id,
        title=body.title,
    )

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to create session")

    session_info = await super_agent_executor.get_session_info(session_id)

    if not session_info:
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

    return SuperAgentSessionResponse(**session_info)


@router.get("/super-agent/sessions/{session_id}", response_model=SuperAgentSessionResponse)
async def get_super_agent_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Get Super Agent session details."""
    from app.super_agents.agent_executor import super_agent_executor

    session_info = await super_agent_executor.get_session_info(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return SuperAgentSessionResponse(**session_info)


@router.get("/super-agent/sessions/{session_id}/messages", response_model=SuperAgentMessageList)
async def get_super_agent_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get Super Agent session messages."""
    from app.super_agents.memory.session_memory import SessionMemory

    messages = await SessionMemory.get_recent_messages(
        db=db,
        session_id=session_id,
        limit=limit,
    )

    return SuperAgentMessageList(
        items=[
            _serialize_super_agent_message(
                {
                    **msg,
                    "session_id": msg.get("session_id") or session_id,
                }
            )
            for msg in messages
        ],
        total=len(messages),
    )


@router.post("/super-agent/sessions/{session_id}/message", response_model=SuperAgentChatResponse)
async def send_super_agent_message(
    session_id: str,
    body: SuperAgentMessageSend,
    company_id: str = Query(..., description="Company ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
):
    """Send a message to the Super Agent."""
    from app.super_agents.agent_executor import super_agent_executor

    result = await super_agent_executor.process_message(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        message=body.message,
    )

    if result.get("error") and not result.get("response"):
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {result['error']}",
        )

    return SuperAgentChatResponse(
        session_id=session_id,
        message_id="",  # Will be filled by the executor
        response=result["response"],
        thinking=result.get("thinking"),
        intent=result.get("intent"),
        tool_calls=result.get("tool_calls") or None,
        tool_used=None,
        interaction_count=0,
        checkpoint_created=result.get("checkpoint_created", False),
    )


@router.get("/super-agent/sessions/{session_id}/checkpoints", response_model=SuperAgentCheckpointList)
async def get_super_agent_checkpoints(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Get Super Agent session checkpoints."""
    from app.models.models import SuperAgentCheckpoint
    from app.schemas.super_agent import SuperAgentCheckpointResponse

    checkpoints = db.query(SuperAgentCheckpoint).filter(
        SuperAgentCheckpoint.session_id == session_id
    ).order_by(SuperAgentCheckpoint.interaction_number.desc()).all()

    return SuperAgentCheckpointList(
        items=[
            SuperAgentCheckpointResponse(
                id=cp.id,
                session_id=cp.session_id,
                interaction_number=cp.interaction_number,
                summary=cp.summary,
                context_snapshot=cp.context_snapshot,
                created_at=cp.created_at,
            )
            for cp in checkpoints
        ],
        total=len(checkpoints),
    )


@router.get("/super-agent/sessions/{session_id}/documents", response_model=SuperAgentDocumentList)
async def get_super_agent_documents(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Get Super Agent session documents."""
    from app.models.models import SuperAgentDocument
    from app.schemas.super_agent import SuperAgentDocumentResponse

    documents = db.query(SuperAgentDocument).filter(
        SuperAgentDocument.session_id == session_id
    ).order_by(SuperAgentDocument.created_at.desc()).all()

    return SuperAgentDocumentList(
        items=[
            SuperAgentDocumentResponse(
                id=doc.id,
                session_id=doc.session_id,
                company_id=doc.company_id,
                filename=doc.filename,
                file_type=doc.file_type,
                content=doc.content,
                content_base64=None,  # Don't return base64 in list
                file_size=doc.file_size,
                description=doc.description,
                created_at=doc.created_at,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.post("/super-agent/knowledge/search", response_model=SuperAgentKnowledgeList)
async def search_super_agent_knowledge(
    body: SuperAgentKnowledgeSearch,
    company_id: str = Query(..., description="Company ID"),
    db: Session = Depends(get_db),
):
    """Search the Super Agent knowledge base."""
    from app.super_agents.memory.knowledge_base import KnowledgeBase

    results = await KnowledgeBase.search(
        db=db,
        company_id=company_id,
        query=body.query,
        category=body.category,
    )

    from app.schemas.super_agent import SuperAgentKnowledgeResponse
    return SuperAgentKnowledgeList(
        items=[SuperAgentKnowledgeResponse(**item) for item in results],
        total=len(results),
    )


@router.post("/super-agent/knowledge", response_model=dict)
async def store_super_agent_knowledge(
    body: SuperAgentKnowledgeStore,
    company_id: str = Query(..., description="Company ID"),
    session_id: Optional[str] = Query(None, description="Source session ID"),
    db: Session = Depends(get_db),
):
    """Store knowledge in the Super Agent knowledge base."""
    from app.super_agents.memory.knowledge_base import KnowledgeBase

    knowledge_id = await KnowledgeBase.store(
        db=db,
        company_id=company_id,
        category=body.category,
        key=body.key,
        value=body.value,
        source_session_id=session_id,
    )

    if not knowledge_id:
        raise HTTPException(status_code=500, detail="Failed to store knowledge")

    return {"success": True, "knowledge_id": knowledge_id}


@router.get("/super-agent/sessions")
async def list_super_agent_sessions(
    company_id: str = Query(..., description="Company ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List Super Agent sessions for a company."""
    from app.super_agents.memory.session_memory import SessionMemory

    sessions = await SessionMemory.list_sessions(
        db=db,
        company_id=company_id,
        user_id=user_id,
        limit=limit,
    )

    return SuperAgentSessionList(
        items=[SuperAgentSessionResponse(**s) for s in sessions],
        total=len(sessions),
    )


# ============== Simplified Chat Endpoint for Frontend ==============


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    body: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simplified endpoint for frontend chat.
    Automatically creates/retrieves session and processes message.
    """
    from app.super_agents.agent_executor import super_agent_executor

    session_id = body.session_id

    if session_id:
        session_info = await _get_authorized_session(
            db=db,
            session_id=session_id,
            current_user=current_user,
        )
        company_id = str(session_info["company_id"])
        user_id = str(session_info["user_id"])
    else:
        company_id, user_id = resolve_agent_chat_actor(
            db=db,
            company_id=body.company_id or current_user.company_id,
            user_id=body.user_id or current_user.id,
        )

    # Create session if not provided
    if not session_id:
        session_id = await _create_agent_session(
            db=db,
            company_id=company_id,
            user_id=user_id,
        )

    # Process message
    result = await super_agent_executor.process_message(
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        message=body.message,
    )

    if result.get("error") and not result.get("response"):
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {result['error']}",
        )

    return AgentChatResponse(
        message_id=str(uuid.uuid4()),
        response=result["response"],
        thinking=result.get("thinking"),
        intent=result.get("intent"),
        tool_calls=result.get("tool_calls") or None,
        session_id=session_id,
    )


@router.post("/chat/session", response_model=AgentChatSessionResponse)
async def create_agent_chat_session(
    body: Optional[AgentChatSessionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = body or AgentChatSessionRequest()
    company_id, user_id = resolve_agent_chat_actor(
        db=db,
        company_id=payload.company_id or current_user.company_id,
        user_id=payload.user_id or current_user.id,
    )

    session_id = await _create_agent_session(
        db=db,
        company_id=company_id,
        user_id=user_id,
    )

    return AgentChatSessionResponse(session_id=session_id)


@router.get("/chat/sessions", response_model=SuperAgentSessionList)
async def list_agent_chat_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id, user_id = resolve_agent_chat_actor(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )

    from app.super_agents.memory.session_memory import SessionMemory

    sessions = await SessionMemory.list_sessions(
        db=db,
        company_id=company_id,
        user_id=user_id,
        limit=limit,
    )

    return SuperAgentSessionList(
        items=[SuperAgentSessionResponse(**session) for session in sessions],
        total=len(sessions),
    )


@router.get("/chat/session/{session_id}/messages", response_model=SuperAgentMessageList)
async def get_agent_chat_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.super_agents.memory.session_memory import SessionMemory

    await _get_authorized_session(
        db=db,
        session_id=session_id,
        current_user=current_user,
    )

    messages = await SessionMemory.get_recent_messages(
        db=db,
        session_id=session_id,
        limit=limit,
    )

    return SuperAgentMessageList(
        items=[
            _serialize_super_agent_message(
                {
                    **message,
                    "session_id": message.get("session_id") or session_id,
                }
            )
            for message in messages
        ],
        total=len(messages),
    )
