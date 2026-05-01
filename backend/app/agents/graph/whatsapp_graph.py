"""WhatsApp Graph - Grafo LangGraph principal do agente WhatsApp."""
from typing import Dict, Any

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312
from app.agents.message_variations import get_error_message
from app.agents.llm_responses import get_error_message_with_tracking

patch_forward_ref_evaluate_for_python312()

from langgraph.graph import StateGraph, END
import structlog

from app.core.config import settings
from app.agents.state import AgentState
from app.agents.graph.nodes import (
    check_human_handoff_node,
    validate_message_node,
    load_context_node,
    classify_intent_node,
    execute_action_node,
    generate_response_node,
)
from app.agents.graph.edges import should_execute_action
from app.services.tool_event_service import generate_request_id

logger = structlog.get_logger()


def create_whatsapp_graph() -> StateGraph:
    """
    Cria e retorna o grafo LangGraph do agente WhatsApp.

    Fluxo:
    0. check_human_handoff: Verifica se conversa está sob controle humano
    1. validate_message: Valida se mensagem deve ser processada
    2. load_context: Carrega contexto da conversa
    3. classify_intent: Classifica intenção da mensagem
    4. (condicional) execute_action: Executa tool se necessário
    5. generate_response: Gera resposta com LLM
    6. END: Finaliza

    Returns:
        StateGraph compilado pronto para uso
    """
    workflow = StateGraph(AgentState)

    # Adicionar nós
    workflow.add_node("check_human_handoff", check_human_handoff_node)
    workflow.add_node("validate_message", validate_message_node)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("generate_response", generate_response_node)

    # Definir ponto de entrada
    workflow.set_entry_point("check_human_handoff")

    # Transições
    workflow.add_edge("check_human_handoff", "validate_message")
    workflow.add_edge("validate_message", "load_context")
    workflow.add_edge("load_context", "classify_intent")

    # Condicional após classificação
    workflow.add_conditional_edges(
        "classify_intent",
        should_execute_action,
        {
            "execute_action": "execute_action",
            "generate_response": "generate_response",
        }
    )

    # Após executar ação, gerar resposta
    workflow.add_edge("execute_action", "generate_response")

    # Após gerar resposta, finalizar
    workflow.add_edge("generate_response", END)

    # Compilar o grafo
    app = workflow.compile()

    logger.info("WhatsApp agent graph compiled successfully")
    return app


class WhatsAppAgentGraph:
    """
    Wrapper para o grafo LangGraph do agente WhatsApp.
    Facilita a execução e gerenciamento do grafo.
    """

    def __init__(self):
        self.graph = create_whatsapp_graph()

    async def run(
        self,
        conversation_id: str,
        instance_id: str,
        instance_name: str,
        remote_jid: str,
        contact_name: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        Executa o grafo do agente com uma mensagem.

        Args:
            conversation_id: ID da conversa
            instance_id: ID da instância WhatsApp
            remote_jid: JID do contato
            contact_name: Nome do contato
            message: Conteúdo da mensagem

        Returns:
            Estado final com a resposta do agente
        """
        initial_state: AgentState = {
            "conversation_id": conversation_id,
            "instance_id": instance_id,
            "instance_name": instance_name,
            "remote_jid": remote_jid,
            "contact_name": contact_name,
            "request_id": generate_request_id(),
            "messages": [],
            "current_message": message,
            "_history_text": None,
            "intent": None,
            "intent_confidence": None,
            "flow_stage": None,
            "active_agent_type": None,
            "human_in_loop": None,
            "human_handoff_reason": None,
            "ticket_id": None,
            "cardapio_context": None,
            "cardapio_items": None,
            "pedido_atual": None,
            "pedido_total": None,
            "cliente_nome": None,
            "cliente_endereco": None,
            "cliente_telefone": None,
            "forma_pagamento": None,
            "coleta_etapa": None,
            "response": None,
            "tool_calls": [],
            "output_type": None,
            "output_data": None,
            "should_respond": True,
            "error": None,
            "correlation_id": None,
        }

        logger.info(
            "Running WhatsApp agent graph",
            conversation_id=conversation_id,
            message_preview=message[:50]
        )

        try:
            logger.info("Graph ainvoke starting", step="invoke_start")
            final_state = await self.graph.ainvoke(initial_state)
            logger.info("Graph ainvoke completed", step="invoke_complete")

            logger.info(
                "Agent graph completed",
                conversation_id=conversation_id,
                has_response=bool(final_state.get("response")),
                intent=final_state.get("intent")
            )

            return final_state

        except Exception as e:
            import traceback
            from app.agents.exceptions import (
                InferenceError,
                ContextLoadError,
                IntentClassificationError,
                ResponseGenerationError,
                ToolExecutionError,
                EvolutionAPIError,
            )
            from app.services.gemini_inference_service import (
                GeminiInferenceServiceError,
                GeminiInferenceTimeoutError,
                GeminiInferenceRateLimitError,
            )
            from app.services.vertex_inference_service import (
                VertexInferenceServiceError,
                VertexInferenceTimeoutError,
                VertexInferenceRateLimitError,
            )

            error_traceback = traceback.format_exc()
            error_type = type(e).__name__
            error_message = str(e)

            # Log detalhado do erro
            logger.error(
                "Agent graph execution failed",
                error=error_message,
                error_type=error_type,
                traceback=error_traceback,
                step="graph_invoke_failed"
            )

            # Determinar mensagem de erro baseada no tipo de exceção
            # Usar variações de banco para mensagens mais naturais
            error_type_map = {
                "InferenceError": "inference",
                "GeminiInferenceServiceError": "inference",
                "VertexInferenceServiceError": "inference",
                "GeminiInferenceTimeoutError": "timeout",
                "VertexInferenceTimeoutError": "timeout",
                "GeminiInferenceRateLimitError": "timeout",
                "VertexInferenceRateLimitError": "timeout",
                "ContextLoadError": "context_load",
                "IntentClassificationError": "intent_classification",
                "ResponseGenerationError": "response_generation",
                "ToolExecutionError": "tool_execution",
                "EvolutionAPIError": "evolution_api",
            }
            
            error_key = error_type_map.get(error_type, "generico")
            user_message = get_error_message(error_key)

            # Em desenvolvimento, incluir mais detalhes no erro
            if settings.DEBUG:
                user_message += f"\n\n[Debug: {error_type}: {error_message}]"

            return {
                **initial_state,
                "response": user_message,
                "error": error_message,
                "error_type": error_type,
            }
