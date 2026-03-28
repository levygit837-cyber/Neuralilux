"""Super Agent graph state definitions."""
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import BaseMessage
import operator


class SuperAgentState(TypedDict):
    """
    Main state for the Super Agent (Business Assistant).
    Flows between graph nodes during message processing.
    """
    # Identification
    session_id: str
    company_id: str
    user_id: str

    # Messages (LangChain format)
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Current user message
    current_message: str
    request_id: str

    # Intent classification
    intent: Optional[str]  # "database_query", "whatsapp_action", "document_creation", "analysis", "knowledge_store", "general"

    # Database query context
    db_query_result: Optional[Dict[str, Any]]
    db_query_sql: Optional[str]

    # WhatsApp context
    whatsapp_action: Optional[str]  # "read_messages", "send_message", "send_bulk"
    whatsapp_target: Optional[str]
    whatsapp_result: Optional[Dict[str, Any]]

    # Document creation context
    document_type: Optional[str]  # "pdf", "txt", "json", "markdown"
    document_content: Optional[str]
    document_id: Optional[str]

    # Thinking process
    thinking_content: Optional[str]

    # Knowledge base context
    knowledge_query: Optional[str]
    knowledge_result: Optional[Dict[str, Any]]

    # Menu and web context
    menu_result: Optional[Dict[str, Any]]
    web_result: Optional[Dict[str, Any]]

    # Tool execution metadata
    tool_calls: Optional[List[Dict[str, Any]]]
    pending_action: Optional[Dict[str, Any]]
    skip_model_response: bool

    # Checkpoint context
    needs_checkpoint: bool
    checkpoint_summary: Optional[str]

    # Response
    response: Optional[str]

    # Error handling
    error: Optional[str]
    should_respond: bool