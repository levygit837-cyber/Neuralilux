"""
Agent Executor - Orquestrador principal do agente WhatsApp.
Responsável por receber mensagens, executar o grafo e enviar respostas.
"""
from typing import Optional, Dict, Any
import structlog
import uuid

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312
from app.agents.exceptions import (
    WhatsAppAgentError,
    MessageProcessingError,
    InferenceError,
    EvolutionAPIError,
    ResponseGenerationError,
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


patch_forward_ref_evaluate_for_python312()

from app.agents.graph.whatsapp_graph import WhatsAppAgentGraph
from app.agents.message_variations import get_error_message
from app.agents.tools.pedido_tool import set_active_conversation, _pedidos_ativos
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()


async def _emit_thinking_event(
    instance_name: str,
    conversation_id: str,
    event: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a thinking event to the frontend via the realtime event bus."""
    try:
        await realtime_event_bus.publish({
            "instance_name": instance_name,
            "type": "thinking",
            "payload": {
                "conversation_id": conversation_id,
                "event": event,
                "data": data or {},
            },
        })
    except Exception as exc:
        logger.warning("Failed to emit thinking event", error=str(exc), event_type=event)


class WhatsAppAgent:
    """
    Agente WhatsApp principal.
    Orquestra o processamento de mensagens recebidas via WhatsApp.
    """

    def __init__(self):
        self.agent_graph = WhatsAppAgentGraph()
        logger.info("WhatsApp Agent initialized")

    async def process_message(
        self,
        conversation_id: str,
        instance_id: str,
        instance_name: str,
        remote_jid: str,
        contact_name: str,
        message: str,
    ) -> Optional[str]:
        """
        Processa uma mensagem recebida do WhatsApp.

        Args:
            conversation_id: ID da conversa no banco de dados
            instance_id: ID da instância WhatsApp
            instance_name: Nome da instância (para envio via Evolution API)
            remote_jid: JID do contato WhatsApp
            contact_name: Nome do contato
            message: Conteúdo da mensagem recebida

        Returns:
            Resposta gerada pelo agente ou None se não deve responder
        """
        correlation_id = str(uuid.uuid4())
        
        logger.info(
            "Processing WhatsApp message",
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            instance_id=instance_id,
            instance_name=instance_name,
            contact=contact_name,
            remote_jid=remote_jid,
            message_preview=message[:50],
            message_length=len(message)
        )

        try:
            logger.info(
                "Starting agent processing",
                correlation_id=correlation_id,
                step="init"
            )

            # Configurar contexto do pedido para esta conversa
            set_active_conversation(conversation_id)
            logger.info(
                "Conversation context set",
                correlation_id=correlation_id,
                step="context_set"
            )

            # Emit thinking start event
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_start",
            )
            logger.info(
                "Thinking event emitted",
                correlation_id=correlation_id,
                step="thinking_start"
            )

            # Executar o grafo do agente
            logger.info(
                "Running agent graph",
                correlation_id=correlation_id,
                step="graph_start"
            )
            result = await self.agent_graph.run(
                conversation_id=conversation_id,
                instance_id=instance_id,
                instance_name=instance_name,
                remote_jid=remote_jid,
                contact_name=contact_name,
                message=message,
            )
            logger.info(
                "Agent graph completed",
                correlation_id=correlation_id,
                step="graph_complete",
                result_keys=list(result.keys()) if result else None
            )

            response = result.get("response")

            # Emit thinking end event with summary
            intent = result.get("intent", "outro")
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_end",
                data={
                    "summary": "",  # No mock thinking, real thinking comes from LLM
                    "intent": intent,
                },
            )

            if not response:
                logger.warning(
                    "Agent returned no response",
                    correlation_id=correlation_id,
                    conversation_id=conversation_id,
                    intent=result.get("intent")
                )
                return None

            # Enviar resposta via Evolution API
            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=response,
                correlation_id=correlation_id
            )

            logger.info(
                "Message processed and response sent",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                response_length=len(response)
            )

            return response

        except (InferenceError, ResponseGenerationError, GeminiInferenceServiceError, GeminiInferenceTimeoutError, GeminiInferenceRateLimitError,
                VertexInferenceServiceError, VertexInferenceTimeoutError, VertexInferenceRateLimitError) as e:
            # Erros específicos de inferência/geração - log detalhado
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(
                "Agent inference/generation error",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                error_type=type(e).__name__,
                error=str(e),
                context=getattr(e, 'context', {}),
                traceback=error_traceback
            )

            # Enviar mensagem de erro mais específica
            from app.core.config import settings

            # Mensagem baseada no tipo de erro usando variações
            timeout_errors = (GeminiInferenceTimeoutError, GeminiInferenceRateLimitError, VertexInferenceTimeoutError, VertexInferenceRateLimitError)
            if isinstance(e, timeout_errors):
                error_msg = get_error_message("timeout")
            else:
                error_msg = get_error_message("inference")

            if settings.DEBUG:
                error_msg += f"\n\n[Debug: {type(e).__name__}: {str(e)}]"

            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=error_msg,
                correlation_id=correlation_id
            )

            return error_msg

        except EvolutionAPIError as e:
            # Erro de comunicação com Evolution API
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(
                "Evolution API communication error",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                instance_name=instance_name,
                remote_jid=remote_jid,
                error_type=type(e).__name__,
                error=str(e),
                context=e.context if hasattr(e, 'context') else {},
                traceback=error_traceback
            )

            # Não enviar mensagem de erro ao cliente pois não conseguimos comunicar
            return None

        except WhatsAppAgentError as e:
            # Outros erros customizados do agente
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(
                "WhatsApp Agent error",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                error_type=type(e).__name__,
                error=str(e),
                context=e.context if hasattr(e, 'context') else {},
                traceback=error_traceback
            )

            from app.core.config import settings
            error_msg = get_error_message("generico")

            if settings.DEBUG:
                error_msg += f"\n\n[Debug: {type(e).__name__}: {str(e)}]"

            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=error_msg,
                correlation_id=correlation_id
            )

            return error_msg

        except Exception as e:
            # Erro genérico não esperado
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(
                "Unexpected error processing message",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=error_traceback
            )

            # Enviar mensagem de erro genérica para erros inesperados
            from app.core.config import settings
            error_msg = get_error_message("generico")

            if settings.DEBUG:
                error_msg += f"\n\n[Debug: {type(e).__name__}: {str(e)}]"

            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=error_msg,
                correlation_id=correlation_id
            )

            return error_msg

    async def _send_response(
        self,
        instance_name: str,
        remote_jid: str,
        response: str,
        correlation_id: str | None = None
    ) -> bool:
        """
        Envia a resposta via Evolution API.

        Args:
            instance_name: Nome da instância WhatsApp
            remote_jid: JID do destinatário
            response: Texto da resposta
            correlation_id: ID de correlação para tracing

        Returns:
            True se enviado com sucesso, False caso contrário

        Raises:
            EvolutionAPIError: Se a comunicação com Evolution API falhar
        """
        try:
            from app.services.evolution_api import EvolutionAPIService

            evolution = EvolutionAPIService()
            result = await evolution.send_text_message(
                instance_name=instance_name,
                remote_jid=remote_jid,
                text=response
            )

            logger.info(
                "Response sent via Evolution API",
                correlation_id=correlation_id,
                instance=instance_name,
                remote_jid=remote_jid,
                response_length=len(response)
            )
            return True

        except Exception as e:
            error_context = {
                "instance_name": instance_name,
                "remote_jid": remote_jid,
                "response_length": len(response)
            }
            logger.error(
                "Failed to send response via Evolution API",
                correlation_id=correlation_id,
                instance=instance_name,
                remote_jid=remote_jid,
                error=str(e),
                error_type=type(e).__name__,
                context=error_context
            )
            raise EvolutionAPIError(
                f"Failed to send response via Evolution API: {str(e)}",
                context=error_context
            ) from e

    def get_pedido_atual(self, conversation_id: str) -> list:
        """Retorna o pedido atual de uma conversa."""
        return _pedidos_ativos.get(conversation_id, [])


# Instância singleton do agente
whatsapp_agent = WhatsAppAgent()
