"""Super Agent LangGraph nodes — native tool-calling agent loop."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.services.inference_service import get_inference_service_with_fallback
from app.services.realtime_event_bus import realtime_event_bus
from app.services.tool_event_service import ToolEventTracker
from app.super_agents.prompts import SUPER_AGENT_SYSTEM_PROMPT
from app.super_agents.state import SuperAgentState
from app.super_agents.tools.tool_dispatcher import dispatch_tool_call
from app.super_agents.tools.tool_schemas import SUPER_AGENT_TOOLS

logger = structlog.get_logger()

MAX_TOOL_ITERATIONS = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _emit(instance_name: str, conversation_id: str, event: str, data: Dict[str, Any] | None = None) -> None:
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
        logger.warning("Failed to emit event", error=str(exc), event_name=event)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Node 1: load_context
# ---------------------------------------------------------------------------

async def load_context_node(state: SuperAgentState) -> Dict[str, Any]:
    """Load company context, session history, RAG context, and build the system prompt."""
    try:
        from app.core.database import get_db
        from app.models.models import Company
        from app.super_agents.memory.session_memory import SessionMemory
        from app.rag.retriever import get_rag_retriever

        db_gen = get_db()
        db = next(db_gen)

        try:
            company = db.query(Company).filter(Company.id == state["company_id"]).first()
            company_name = company.name if company else "Empresa"
            business_type = company.business_type_id if company else "Geral"

            recent_messages = await SessionMemory.get_recent_messages(db, state["session_id"], limit=10)
            lc_messages: list = []
            for msg in recent_messages:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"] or ""))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"] or ""))

            base_system_prompt = SUPER_AGENT_SYSTEM_PROMPT.format(
                company_name=company_name,
                business_type=business_type,
                company_id=state["company_id"],
            )

            rag_context = ""
            pdf_content = state.get("document_content")
            current_message = state.get("current_message", "")

            if current_message or pdf_content:
                try:
                    retriever = get_rag_retriever()
                    rag_result = await retriever.retrieve(
                        company_id=state["company_id"],
                        message=current_message,
                        pdf_content=pdf_content,
                        limit=5,
                    )
                    rag_context = retriever.build_context_prompt(rag_result)
                except Exception as rag_err:
                    logger.warning("RAG retrieval failed", error=str(rag_err))

            if rag_context:
                system_prompt = f"{base_system_prompt}\n\n{rag_context}"
            else:
                system_prompt = base_system_prompt

            # Build agent_messages in OpenAI dict format for the tool-calling loop
            agent_msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            for msg in recent_messages:
                if msg["role"] == "user":
                    agent_msgs.append({"role": "user", "content": msg["content"] or ""})
                elif msg["role"] == "assistant":
                    agent_msgs.append({"role": "assistant", "content": msg["content"] or ""})

            thinking = f"Contexto carregado: Empresa '{company_name}', {len(lc_messages)} mensagens recentes."
            if rag_context:
                thinking += " Contexto RAG injetado."

            logger.info("Context loaded", session_id=state["session_id"], company=company_name, message_count=len(lc_messages), rag_enabled=bool(rag_context))

            return {
                "messages": [SystemMessage(content=system_prompt)] + lc_messages,
                "agent_messages": agent_msgs,
                "thinking_content": thinking,
            }
        finally:
            db.close()

    except Exception as e:
        logger.error("Failed to load context", error=str(e))
        return {"thinking_content": f"Erro ao carregar contexto: {e}"}


# ---------------------------------------------------------------------------
# Node 2: agent_loop — ReAct loop with native tool calling
# ---------------------------------------------------------------------------

async def agent_loop_node(state: SuperAgentState) -> Dict[str, Any]:
    """
    Core agent loop using native tool calling.

    1. Send messages + tools to LLM via chat_completion_with_tools
    2. If model returns tool_calls → dispatch each, append results, loop
    3. If model returns content only → return as final response
    """
    conversation_id = state.get("session_id", "unknown")
    instance_name = state.get("company_id", "default")
    company_id = state.get("company_id", "")
    session_id = state.get("session_id")
    request_id = state.get("request_id")

    await _emit(instance_name, conversation_id, "thinking_start")

    agent_messages = list(state.get("agent_messages") or [])
    agent_messages.append({"role": "user", "content": state["current_message"]})

    inference_svc = get_inference_service_with_fallback("super_agent")
    all_tool_calls: List[Dict[str, Any]] = []
    thinking_parts: List[str] = []
    response_text = ""
    response_started = False  # Track if we've emitted response_start
    event_sequence: List[Dict[str, Any]] = []  # Track event sequence for debugging

    # Helper to track events
    def _track_event(event: str, data_size: int = 0) -> None:
        event_sequence.append({
            "event": event,
            "timestamp": _now_iso(),
            "data_size": data_size,
        })

    # Create a ToolEventTracker so tool lifecycle events go through the
    # proper "tool_event" pipeline (not "thinking"), which the frontend
    # expects for rendering tool cards.
    tool_tracker = ToolEventTracker(
        source="super_agent",
        instance_name=instance_name,
        conversation_id=conversation_id,
        request_id=request_id or "",
        session_id=session_id,
    )

    try:
        await _emit(instance_name, conversation_id, "thinking_start")
        _track_event("thinking_start")

        for iteration in range(MAX_TOOL_ITERATIONS):
            await _emit(
                instance_name, conversation_id, "thinking_token",
                {"token": f"🔄 Iteração {iteration + 1}...\n"},
            )

            # Callback that streams each thinking token to the frontend
            async def _on_thinking_token(token: str) -> None:
                await _emit(
                    instance_name, conversation_id, "thinking_token",
                    {"token": token},
                )
                _track_event("thinking_token", len(token))

            # Callback that streams response tokens in real-time
            async def _on_response_token(token: str) -> None:
                nonlocal response_started, response_text

                # If this is the first response token, emit start events
                if not response_started:
                    thinking_content = "\n".join(thinking_parts)
                    summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"
                    await _emit(instance_name, conversation_id, "thinking_end", {"summary": summary})
                    _track_event("thinking_end", len(summary))
                    await _emit(instance_name, conversation_id, "response_start")
                    _track_event("response_start")
                    response_started = True

                # Stream the token immediately
                await _emit(
                    instance_name, conversation_id, "response_token",
                    {"token": token},
                )
                _track_event("response_token", len(token))

                # Accumulate for final response_end event
                response_text += token

            result = await inference_svc.stream_chat_completion_with_tools(
                messages=agent_messages,
                tools=SUPER_AGENT_TOOLS,
                max_tokens=2048,
                temperature=0.4,
                on_thinking_token=_on_thinking_token,
                on_response_token=_on_response_token,
            )

            tool_calls = result.get("tool_calls") or []
            content = result.get("content") or ""

            if not tool_calls:
                # No tools requested — this is the final answer
                # Note: response_text is already accumulated by _on_response_token callback
                # If streaming didn't happen (no callback was triggered), use content directly
                if content and not response_started:
                    # Fallback: content arrived but wasn't streamed (shouldn't happen normally)
                    thinking_content = "\n".join(thinking_parts)
                    summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"
                    await _emit(instance_name, conversation_id, "thinking_end", {"summary": summary})
                    await _emit(instance_name, conversation_id, "response_start")
                    response_started = True

                    # Stream the content token by token to avoid sending huge chunks
                    for char in content:
                        await _emit(instance_name, conversation_id, "response_token", {"token": char})

                    response_text = content

                if content:
                    thinking_parts.append(f"Resposta final gerada (iteração {iteration + 1}).")
                break

            # Model wants to call tools — build assistant message with tool_calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": json.dumps(tc["function"]["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            agent_messages.append(assistant_msg)

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]
                tool_id = tc["id"]

                display_name = tool_name.replace("_", " ").title()

                await _emit(
                    instance_name, conversation_id, "thinking_token",
                    {"token": f"Executando ferramenta: {tool_name}...\n"},
                )

                # Emit tool_started via ToolEventTracker (type=tool_event, phase=started)
                handle = tool_tracker.start(
                    tool_name,
                    input_payload=tool_args,
                    display_name=display_name,
                )

                dispatch_result = await dispatch_tool_call(
                    name=tool_name,
                    arguments=tool_args,
                    company_id=company_id,
                    session_id=session_id,
                )

                tool_output = dispatch_result.get("result", {})
                success = dispatch_result.get("success", False)

                # Emit tool_completed or tool_failed via ToolEventTracker
                if success:
                    finished_at = tool_tracker.complete(handle, output_payload=tool_output)
                else:
                    error_msg = dispatch_result.get("error", "Erro na execução da ferramenta")
                    finished_at = tool_tracker.fail(handle, error=str(error_msg), output_payload=tool_output)

                # Serialize output for the model
                output_str = json.dumps(tool_output, ensure_ascii=False, default=str)

                # Append tool result message for the model
                agent_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": output_str,
                })

                # Track for persistence
                all_tool_calls.append({
                    "name": tool_name,
                    "input": tool_args,
                    "output": tool_output,
                    "status": "completed" if success else "failed",
                    "display_name": display_name,
                    "trace_id": handle.trace_id,
                    "started_at": handle.started_at,
                    "finished_at": finished_at,
                })

                thinking_parts.append(f"Ferramenta {tool_name} executada.")

            # Flush pending tool events after each iteration
            await tool_tracker.flush()

        else:
            # Exceeded MAX_TOOL_ITERATIONS — generate final response anyway
            thinking_parts.append(f"Limite de {MAX_TOOL_ITERATIONS} iterações atingido.")

        # If we didn't get a text response from the loop, do a final call without tools
        if not response_text:
            await _emit(instance_name, conversation_id, "thinking_token", {"token": "\n💭 Gerando resposta final...\n"})

            async def _on_final_thinking(token: str) -> None:
                await _emit(
                    instance_name, conversation_id, "thinking_token",
                    {"token": token},
                )

            async def _on_final_response(token: str) -> None:
                """Stream response tokens in real-time as they arrive from LLM."""
                nonlocal response_started, response_text

                # If this is the first response token, emit start events
                if not response_started:
                    thinking_content = "\n".join(thinking_parts)
                    summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"
                    await _emit(instance_name, conversation_id, "thinking_end", {"summary": summary})
                    await _emit(instance_name, conversation_id, "response_start")
                    response_started = True

                # Stream the token immediately
                await _emit(
                    instance_name, conversation_id, "response_token",
                    {"token": token},
                )

                # Accumulate for final response_end event
                response_text += token

            final = await inference_svc.stream_chat_completion_with_tools(
                messages=agent_messages,
                tools=SUPER_AGENT_TOOLS,
                max_tokens=2048,
                temperature=0.7,
                tool_choice="none",
                on_thinking_token=_on_final_thinking,
                on_response_token=_on_final_response,
            )

            # Fallback if streaming didn't produce content
            if not response_text:
                response_text = final.get("content") or "Desculpe, não consegui processar sua solicitação."

        # If response was already streamed during the loop, we don't need to emit anything else
        # The _on_response_token callback already handled thinking_end, response_start, and all tokens

        # Always emit response_end with the final accumulated content
        await _emit(instance_name, conversation_id, "response_end", {"content": response_text})
        _track_event("response_end", len(response_text))

        # Build final thinking content for return
        thinking_content = "\n".join(thinking_parts)
        summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"

        logger.info(
            "Agent loop completed",
            session_id=session_id,
            iterations=len(thinking_parts),
            tool_call_count=len(all_tool_calls),
            response_length=len(response_text),
            response_started=response_started,
            event_sequence=event_sequence,
            event_count=len(event_sequence),
        )

        return {
            "response": response_text,
            "messages": [AIMessage(content=response_text)],
            "thinking_content": thinking_content or summary,
            "tool_calls": all_tool_calls,
            "request_id": request_id,
            "intent": "agent_loop",
        }

    except Exception as e:
        logger.error("Agent loop failed", error=str(e), session_id=session_id, exc_info=True)

        # Ensure thinking is properly closed if it was started
        thinking_content = "\n".join(thinking_parts) if thinking_parts else "Erro durante processamento"
        await _emit(instance_name, conversation_id, "thinking_end", {"summary": thinking_content[:120]})

        # Ensure response events are properly emitted
        error_message = f"Desculpe, ocorreu um erro ao processar sua mensagem: {str(e)}"

        if not response_started:
            # Response never started, emit full sequence
            await _emit(instance_name, conversation_id, "response_start")
            await _emit(instance_name, conversation_id, "response_token", {"token": error_message})
            await _emit(instance_name, conversation_id, "response_end", {"content": error_message})
        else:
            # Response was started but may not have finished
            if not response_text:
                # No content was accumulated, send error message
                await _emit(instance_name, conversation_id, "response_token", {"token": error_message})
            await _emit(instance_name, conversation_id, "response_end", {"content": response_text or error_message})

        return {
            "response": error_message,
            "error": str(e),
            "messages": [AIMessage(content=error_message)],
        }


# ---------------------------------------------------------------------------
# Node 3: handle_checkpoint (unchanged)
# ---------------------------------------------------------------------------

async def handle_checkpoint_node(state: SuperAgentState) -> Dict[str, Any]:
    """Handle checkpoint creation if needed (every 5 interactions)."""
    try:
        from app.core.database import get_db
        from app.super_agents.memory.session_memory import SessionMemory
        from app.super_agents.prompts import CHECKPOINT_SUMMARY_PROMPT

        session_id = state["session_id"]
        db_gen = get_db()
        db = next(db_gen)

        try:
            should_checkpoint = await SessionMemory.should_create_checkpoint(db, session_id)

            if should_checkpoint:
                recent_messages = await SessionMemory.get_recent_messages(db, session_id, limit=10)
                conversation_text = "\n".join([
                    f"{msg['role']}: {(msg['content'] or '')[:200]}"
                    for msg in recent_messages if msg.get("content")
                ])

                summary_prompt = CHECKPOINT_SUMMARY_PROMPT.format(conversation_history=conversation_text)
                inference_service = get_inference_service_with_fallback("super_agent")
                result = await inference_service.chat_completion(
                    messages=[{"role": "user", "content": summary_prompt}],
                    max_tokens=500,
                    temperature=0.5,
                )

                summary = result.get("content", "")
                if summary:
                    await SessionMemory.create_checkpoint(db=db, session_id=session_id, summary=summary)
                    logger.info("Checkpoint created", session_id=session_id)
                    return {"needs_checkpoint": True, "checkpoint_summary": summary}
        finally:
            db.close()

    except Exception as e:
        logger.error("Failed to handle checkpoint", error=str(e))

    return {}
