"""Super Agent Graph - LangGraph construction for the Super Agent."""
from typing import Dict, Any
import structlog

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312
patch_forward_ref_evaluate_for_python312()

from langgraph.graph import StateGraph, END
from app.super_agents.state import SuperAgentState
from app.super_agents.graph.nodes import (
    load_context_node,
    classify_intent_node,
    execute_action_node,
    generate_response_node,
    handle_checkpoint_node,
)
from app.services.tool_event_service import generate_request_id

logger = structlog.get_logger()


def create_super_agent_graph() -> StateGraph:
    """
    Create and return the Super Agent LangGraph.

    Flow:
    1. load_context -> classify_intent -> execute_action -> generate_response -> handle_checkpoint -> END

    Returns:
        Compiled StateGraph ready for use
    """
    workflow = StateGraph(SuperAgentState)

    # Add nodes
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("handle_checkpoint", handle_checkpoint_node)

    # Define entry point
    workflow.set_entry_point("load_context")

    # Transitions
    workflow.add_edge("load_context", "classify_intent")
    workflow.add_edge("classify_intent", "execute_action")
    workflow.add_edge("execute_action", "generate_response")
    workflow.add_edge("generate_response", "handle_checkpoint")
    workflow.add_edge("handle_checkpoint", END)

    # Compile the graph
    app = workflow.compile()
    logger.info("Super Agent graph compiled successfully")
    return app


class SuperAgentGraph:
    """
    Wrapper for the Super Agent LangGraph.
    """

    def __init__(self):
        self.graph = create_super_agent_graph()

    async def run(
        self,
        session_id: str,
        company_id: str,
        user_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        Execute the Super Agent graph with a message.

        Args:
            session_id: Session ID
            company_id: Company ID
            user_id: User ID
            message: User message content

        Returns:
            Final state with agent response
        """
        initial_state: SuperAgentState = {
            "session_id": session_id,
            "company_id": company_id,
            "user_id": user_id,
            "messages": [],
            "current_message": message,
            "request_id": generate_request_id(),
            "intent": None,
            "db_query_result": None,
            "db_query_sql": None,
            "whatsapp_action": None,
            "whatsapp_target": None,
            "whatsapp_result": None,
            "document_type": None,
            "document_content": None,
            "document_id": None,
            "thinking_content": None,
            "knowledge_query": None,
            "knowledge_result": None,
            "menu_result": None,
            "web_result": None,
            "tool_calls": [],
            "pending_action": None,
            "skip_model_response": False,
            "needs_checkpoint": False,
            "checkpoint_summary": None,
            "response": None,
            "error": None,
            "should_respond": True,
        }

        logger.info(
            "Running Super Agent graph",
            session_id=session_id,
            message_preview=message[:50],
        )

        try:
            final_state = await self.graph.ainvoke(initial_state)
            logger.info(
                "Super Agent graph completed",
                session_id=session_id,
                has_response=bool(final_state.get("response")),
                intent=final_state.get("intent"),
            )
            return final_state

        except Exception as e:
            logger.error("Super Agent graph execution failed", error=str(e))
            return {
                **initial_state,
                "response": f"Desculpe, ocorreu um erro ao processar sua mensagem: {str(e)}",
                "error": str(e),
            }