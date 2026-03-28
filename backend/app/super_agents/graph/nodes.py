"""
Super Agent Graph Nodes - Individual nodes for the LangGraph.
"""
from typing import Dict, Any
import json
import structlog

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.super_agents.state import SuperAgentState
from app.super_agents.prompts import SUPER_AGENT_SYSTEM_PROMPT, INTENT_CLASSIFICATION_PROMPT
from app.services.inference_service import inference_service
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()


async def _emit_super_thinking_event(
    instance_name: str,
    conversation_id: str,
    event: str,
    data: Dict[str, Any] = None,
) -> None:
    """Emit a thinking event to the frontend via the realtime event bus."""
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

        result = await inference_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1,
        )

        intent = result.get("content", "general").strip().lower()

        # Validate intent
        valid_intents = [
            "database_query", "whatsapp_action", "document_creation",
            "analysis", "knowledge_store", "general"
        ]

        if intent not in valid_intents:
            # Fallback: simple keyword matching
            message_lower = message.lower()
            if any(kw in message_lower for kw in ["produto", "contato", "cliente", "listar", "quantos", "buscar"]):
                intent = "database_query"
            elif any(kw in message_lower for kw in ["whatsapp", "mensagem", "enviar", "ler conversa"]):
                intent = "whatsapp_action"
            elif any(kw in message_lower for kw in ["documento", "pdf", "relatório", "criar"]):
                intent = "document_creation"
            elif any(kw in message_lower for kw in ["análise", "analisar", "briefing", "insight", "estatística"]):
                intent = "analysis"
            elif any(kw in message_lower for kw in ["anotar", "lembrar", "salvar", "guardar"]):
                intent = "knowledge_store"
            else:
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
        message = state["current_message"]

        thinking = f"Executando ação para intenção: {intent}\n"
        result_data = {}

        if intent == "database_query":
            # Use database query tool
            from app.super_agents.tools.database_tool import database_query_tool
            # The LLM will call the tool via the system prompt
            thinking += "Ação: Consulta ao banco de dados será processada pelo LLM."

        elif intent == "whatsapp_action":
            # Use WhatsApp tools
            thinking += "Ação: Ação WhatsApp será processada pelo LLM."

        elif intent == "document_creation":
            # Use document creation tool
            thinking += "Ação: Criação de documento será processada pelo LLM."

        elif intent == "analysis":
            # Analysis will be done by LLM with data from database
            thinking += "Ação: Análise será gerada pelo LLM com dados do banco."

        elif intent == "knowledge_store":
            # Use knowledge store tool
            thinking += "Ação: Armazenamento de conhecimento será processado pelo LLM."

        else:
            thinking += "Ação: Resposta geral do LLM."

        logger.info(
            "Action executed",
            session_id=state["session_id"],
            intent=intent,
        )

        return {
            "thinking_content": thinking,
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

    try:
        # Build messages for LLM
        messages = list(state.get("messages", []))
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

        # Use streaming inference with thinking detection
        thinking_buffer = []
        response_buffer = []

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
                response_buffer.append(token)

        # Join response tokens into final response
        response = "".join(response_buffer).strip()

        if not response:
            response = "Desculpe, não consegui processar sua solicitação."

        # Create summary from thinking content (first 120 chars)
        thinking_content = "".join(thinking_buffer)
        summary = thinking_content[:120] if thinking_content else "Resposta gerada com sucesso"

        # Emit thinking_end event with summary
        await _emit_super_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": summary},
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
            "thinking_content": state.get("thinking_content", "") + f"\n{summary}",
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
                    "thinking_content": state.get("thinking_content", "") + f"\nCheckpoint criado: {checkpoint_id}",
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