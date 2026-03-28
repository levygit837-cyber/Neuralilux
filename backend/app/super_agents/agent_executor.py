"""Super Agent executor."""
from typing import Optional, Dict, Any
import json
import structlog

from app.super_agents.graph.super_agent_graph import SuperAgentGraph
from app.super_agents.memory.session_memory import SessionMemory

logger = structlog.get_logger()


class SuperAgentExecutor:
    """
    Super Agent (Business Assistant) main executor.
    Orchestrates message processing for company owners/admins.
    """

    def __init__(self):
        self.agent_graph = SuperAgentGraph()
        logger.info("Super Agent Executor initialized")

    async def process_message(
        self,
        session_id: str,
        company_id: str,
        user_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        Process a user message through the Super Agent.

        Args:
            session_id: Session ID
            company_id: Company ID
            user_id: User ID
            message: User message

        Returns:
            Dict with response, thinking, intent, etc.
        """
        logger.info(
            "Processing Super Agent message",
            session_id=session_id,
            company_id=company_id,
            message_preview=message[:50],
        )

        try:
            # Add user message to session
            from app.core.database import get_db
            db_gen = get_db()
            db = next(db_gen)

            try:
                await SessionMemory.add_message(
                    db=db,
                    session_id=session_id,
                    role="user",
                    content=message,
                )
            finally:
                db.close()

            # Execute the graph
            result = await self.agent_graph.run(
                session_id=session_id,
                company_id=company_id,
                user_id=user_id,
                message=message,
            )

            response = result.get("response", "")
            thinking = result.get("thinking_content", "")
            intent = result.get("intent", "general")
            needs_checkpoint = result.get("needs_checkpoint", False)
            pending_action = result.get("pending_action")
            tool_calls = result.get("tool_calls") or []
            request_id = result.get("request_id")

            # Add assistant message to session
            db_gen = get_db()
            db = next(db_gen)

            try:
                for tool_call in tool_calls:
                    await SessionMemory.add_message(
                        db=db,
                        session_id=session_id,
                        role="tool",
                        tool_name=tool_call.get("name"),
                        tool_input=tool_call.get("input"),
                        tool_output=json.dumps(tool_call.get("output"), ensure_ascii=False, default=str),
                        extra_data={
                            "name": tool_call.get("name"),
                            "display_name": tool_call.get("display_name"),
                            "status": tool_call.get("status"),
                            "trace_id": tool_call.get("trace_id"),
                            "request_id": request_id,
                            "started_at": tool_call.get("started_at"),
                            "finished_at": tool_call.get("finished_at"),
                        },
                    )

                await SessionMemory.add_message(
                    db=db,
                    session_id=session_id,
                    role="assistant",
                    content=response,
                    thinking_content=thinking,
                    extra_data={
                        "intent": intent,
                        "needs_checkpoint": needs_checkpoint,
                        "pending_action": pending_action,
                        "tool_calls": [tool_call.get("name") for tool_call in tool_calls],
                    },
                )
            finally:
                db.close()

            logger.info(
                "Super Agent message processed",
                session_id=session_id,
                intent=intent,
                response_length=len(response),
                checkpoint_created=needs_checkpoint,
            )

            return {
                "response": response,
                "thinking": thinking,
                "intent": intent,
                "tool_calls": tool_calls,
                "request_id": request_id,
                "pending_action": pending_action,
                "checkpoint_created": needs_checkpoint,
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(
                "Super Agent message processing failed",
                session_id=session_id,
                error=str(e),
            )
            return {
                "response": f"Desculpe, ocorreu um erro: {str(e)}",
                "thinking": None,
                "intent": "error",
                "checkpoint_created": False,
                "error": str(e),
            }

    async def create_session(
        self,
        company_id: str,
        user_id: str,
        title: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a new Super Agent session.

        Args:
            company_id: Company ID
            user_id: User ID
            title: Optional session title

        Returns:
            Session ID or None
        """
        from app.core.database import get_db
        db_gen = get_db()
        db = next(db_gen)

        try:
            session_id = await SessionMemory.create_session(
                db=db,
                company_id=company_id,
                user_id=user_id,
                title=title,
            )
            logger.info(
                "Super Agent session created",
                session_id=session_id,
                company_id=company_id,
            )
            return session_id
        finally:
            db.close()

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list:
        """
        Get session message history.

        Args:
            session_id: Session ID
            limit: Maximum messages

        Returns:
            List of messages
        """
        from app.core.database import get_db
        db_gen = get_db()
        db = next(db_gen)

        try:
            return await SessionMemory.get_recent_messages(
                db=db,
                session_id=session_id,
                limit=limit,
            )
        finally:
            db.close()

    async def get_session_info(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get session details.

        Args:
            session_id: Session ID

        Returns:
            Session info dict or None
        """
        from app.core.database import get_db
        db_gen = get_db()
        db = next(db_gen)

        try:
            return await SessionMemory.get_session(
                db=db,
                session_id=session_id,
            )
        finally:
            db.close()


# Singleton instance
super_agent_executor = SuperAgentExecutor()
