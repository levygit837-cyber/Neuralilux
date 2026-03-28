"""Super Agent LangGraph nodes."""
from typing import Dict, Any
import structlog

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.super_agents.state import SuperAgentState
from app.super_agents.prompts import (
    SUPER_AGENT_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    TOOL_RESPONSE_SYSTEM_PROMPT,
)
from app.super_agents.tool_runtime import execute_tools_for_state
from app.services.inference_service import get_inference_service
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()


async def _emit_super_thinking_event(
    instance_name: str,
    conversation_id: str,
    event: str,
    data: Dict[str, Any] | None = None,
) -> None:
    """Emit a streaming event to the frontend via the realtime event bus."""
    try:
        await realtime_event_bus.publish({
            "instance_name": instance_name,
            "type": "thinking",
            "conversationId": conversation_id,
            "payload": {
                "conversation_id": conversation_id,
                "event": event,
                "data": data or {},
            },
        })
    except Exception as exc:
        logger.warning("Failed to emit thinking event", error=str(exc), event=event)


async def load_context_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Load company context, session history, and relevant knowledge.
    """
    try:
        from app.core.database import get_db
        from app.models.models import Company
        from app.super_agents.memory.session_memory import SessionMemory

        db_gen = get_db()
        db = next(db_gen)

        try:
            # Get company info
            company = db.query(Company).filter(
                Company.id == state["company_id"]
            ).first()

            company_name = company.name if company else "Empresa"
            business_type = company.business_type_id if company else "Geral"

            # Load recent messages
            recent_messages = await SessionMemory.get_recent_messages(
                db, state["session_id"], limit=10
            )

            # Build message history
            messages = []
            for msg in recent_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"] or ""))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"] or ""))

            # Build system prompt
            system_prompt = SUPER_AGENT_SYSTEM_PROMPT.format(
                company_name=company_name,
                business_type=business_type,
                company_id=state["company_id"],
            )

            logger.info(
                "Context loaded",
                session_id=state["session_id"],
                company=company_name,
                message_count=len(messages),
            )

            return {
                "messages": [SystemMessage(content=system_prompt)] + messages,
                "thinking_content": f"Contexto carregado: Empresa '{company_name}', {len(messages)} mensagens recentes.",
            }

        finally:
            db.close()

    except Exception as e:
        logger.error("Failed to load context", error=str(e))
        return {
            "thinking_content": f"Erro ao carregar contexto: {str(e)}",
        }


async def classify_intent_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Classify the user's intent from their message.
    """
    try:
        message = state["current_message"]

        # Use LLM to classify intent
        prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)

        inference_service = get_inference_service("super_agent")
        result = await inference_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1,
        )

        intent = result.get("content", "general").strip().lower()

        valid_intents = {
            "database_query",
            "whatsapp_action",
            "document_creation",
            "analysis",
            "knowledge_store",
            "general",
        }
        if intent not in valid_intents:
            intent = "general"

        logger.info(
            "Intent classified",
            session_id=state["session_id"],
            intent=intent,
            message_preview=message[:50],
        )

        return {
            "intent": intent,
            "thinking_content": f"Intenção classificada: {intent}",
        }

    except Exception as e:
        logger.error("Failed to classify intent", error=str(e))
        return {
            "intent": "general",
            "thinking_content": f"Erro na classificação, usando 'general': {str(e)}",
        }


async def execute_action_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Execute the appropriate tool/action based on classified intent.
    """
    try:
        intent = state.get("intent", "general")
        result_data = await execute_tools_for_state(state)
        previous_thinking = (state.get("thinking_content") or "").strip()
        current_thinking = (result_data.get("thinking_content") or "").strip()
        combined_thinking = "\n".join(part for part in [previous_thinking, current_thinking] if part)

        logger.info(
            "Action executed",
            session_id=state["session_id"],
            intent=intent,
            tool_call_count=len(result_data.get("tool_calls") or []),
            skip_model_response=result_data.get("skip_model_response", False),
        )

        return {
            "thinking_content": combined_thinking,
            **result_data,
        }

    except Exception as e:
        logger.error("Failed to execute action", error=str(e))
        return {
            "error": str(e),
            "thinking_content": f"Erro ao executar ação: {str(e)}",
        }


async def generate_response_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Generate the final response using the LLM with streaming and thinking detection.
    """
    conversation_id = state.get("session_id", "unknown")
    instance_name = state.get("company_id", "default")

    if state.get("skip_model_response") and state.get("response"):
        direct_thinking = (state.get("thinking_content") or "").strip()
        summary = direct_thinking[:120] if direct_thinking else "Resposta gerada com ferramentas"
        await _emit_super_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_start",
        )
        await _emit_super_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": summary},
        )
        return {
            "response": state.get("response"),
            "messages": [AIMessage(content=state.get("response") or "")],
            "thinking_content": direct_thinking or summary,
            "tool_calls": state.get("tool_calls") or [],
            "request_id": state.get("request_id"),
        }

    try:
        # Build messages for LLM
        messages = list(state.get("messages", []))
        if state.get("tool_calls"):
            tool_context = "\n".join(
                f"- {call.get('name')}: {call.get('output')}"
                for call in (state.get("tool_calls") or [])
            )
            messages.append(SystemMessage(content=TOOL_RESPONSE_SYSTEM_PROMPT))
            messages.append(SystemMessage(content=f"Contexto de ferramentas já executadas:\n{tool_context}"))
        messages.append(HumanMessage(content=state["current_message"]))

        # Convert to dict format for inference service
        msg_dicts = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                msg_dicts.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                msg_dicts.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msg_dicts.append({"role": "assistant", "content": msg.content})

        # Emit thinking_start event
        await _emit_super_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_start",
        )

        # Use streaming inference with thinking/response detection
        thinking_buffer = []
        response_buffer = []
        thinking_end_emitted = False
        response_started = False

        inference_service = get_inference_service("super_agent")
        async for token_type, token in inference_service.astream_chat_completion_with_thinking(
            messages=msg_dicts,
            max_tokens=2000,
            temperature=0.7,
        ):
            if token_type == "thinking":
                thinking_buffer.append(token)
                # Publish thinking_token event
                await _emit_super_thinking_event(
                    instance_name=instance_name,
                    conversation_id=conversation_id,
                    event="thinking_token",
                    data={"token": token},
                )
            elif token_type == "response":
                if not thinking_end_emitted:
                    interim_thinking = "".join(thinking_buffer).strip()
                    interim_summary = interim_thinking[:120] if interim_thinking else "Resposta gerada com sucesso"
                    await _emit_super_thinking_event(
                        instance_name=instance_name,
                        conversation_id=conversation_id,
                        event="thinking_end",
                        data={"summary": interim_summary},
                    )
                    thinking_end_emitted = True

                if not response_started:
                    await _emit_super_thinking_event(
                        instance_name=instance_name,
                        conversation_id=conversation_id,
                        event="response_start",
                    )
                    response_started = True

                response_buffer.append(token)
                await _emit_super_thinking_event(
                    instance_name=instance_name,
                    conversation_id=conversation_id,
                    event="response_token",
                    data={"token": token},
                )

        # Create summary from thinking content (first 120 chars)
        thinking_content = "".join(thinking_buffer).strip()
        summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"
        persisted_thinking = thinking_content or (state.get("thinking_content") or "").strip() or summary

        # Join response tokens into final response
        response = "".join(response_buffer).strip()

        if not response and thinking_content:
            response = thinking_content

        if not response:
            response = "Desculpe, não consegui processar sua solicitação."

        if not thinking_end_emitted:
            await _emit_super_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_end",
                data={"summary": summary},
            )

        if response_started:
            await _emit_super_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="response_end",
                data={"content": response},
            )

        logger.info(
            "Response generated",
            session_id=state["session_id"],
            response_length=len(response),
            thinking_length=len(thinking_content),
        )

        return {
            "response": response,
            "messages": [AIMessage(content=response)],
            "thinking_content": persisted_thinking,
            "tool_calls": state.get("tool_calls") or [],
            "request_id": state.get("request_id"),
        }

    except Exception as e:
        logger.error("Failed to generate response", error=str(e), session_id=conversation_id)

        # Emit thinking_end with error summary
        await _emit_super_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": "Erro ao gerar resposta"},
        )

        return {
            "response": f"Desculpe, ocorreu um erro ao processar sua mensagem: {str(e)}",
            "error": str(e),
        }


async def handle_checkpoint_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Handle checkpoint creation if needed (every 5 interactions).
    """
    try:
        from app.core.database import get_db
        from app.super_agents.memory.session_memory import SessionMemory

        session_id = state["session_id"]

        db_gen = get_db()
        db = next(db_gen)

        try:
            should_checkpoint = await SessionMemory.should_create_checkpoint(
                db, session_id
            )

            if should_checkpoint:
                # Generate summary of recent conversation
                recent_messages = await SessionMemory.get_recent_messages(
                    db, session_id, limit=10
                )

                conversation_text = "\n".join([
                    f"{msg['role']}: {msg['content'][:200]}"
                    for msg in recent_messages if msg.get("content")
                ])

                # Use LLM to generate summary
                from app.super_agents.prompts import CHECKPOINT_SUMMARY_PROMPT
                summary_prompt = CHECKPOINT_SUMMARY_PROMPT.format(
                    conversation_history=conversation_text
                )

                inference_service = get_inference_service("super_agent")
                result = await inference_service.chat_completion(
                    messages=[{"role": "user", "content": summary_prompt}],
                    max_tokens=500,
                    temperature=0.5,
                )

                summary = result.get("content", "Resumo não disponível.")

                # Create checkpoint
                checkpoint_id = await SessionMemory.create_checkpoint(
                    db=db,
                    session_id=session_id,
                    summary=summary,
                    context_snapshot={
                        "intent": state.get("intent"),
                        "interaction_count": state.get("interaction_count", 0),
                    },
                )

                logger.info(
                    "Checkpoint created",
                    session_id=session_id,
                    checkpoint_id=checkpoint_id,
                )

                return {
                    "needs_checkpoint": True,
                    "checkpoint_summary": summary,
                    "thinking_content": (state.get("thinking_content") or "") + f"\nCheckpoint criado: {checkpoint_id}",
                }
            else:
                return {
                    "needs_checkpoint": False,
                }

        finally:
            db.close()

    except Exception as e:
        logger.error("Failed to handle checkpoint", error=str(e))
        return {
            "needs_checkpoint": False,
            "error": str(e),
        }
