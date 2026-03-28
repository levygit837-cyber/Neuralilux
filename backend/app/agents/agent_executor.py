"""
Agent Executor - Orquestrador principal do agente WhatsApp.
Responsável por receber mensagens, executar o grafo e enviar respostas.
"""
from typing import Optional, Dict, Any
import structlog

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312


patch_forward_ref_evaluate_for_python312()

from app.agents.graph.whatsapp_graph import WhatsAppAgentGraph
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
        logger.warning("Failed to emit thinking event", error=str(exc), event=event)


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
        logger.info(
            "Processing WhatsApp message",
            conversation_id=conversation_id,
            contact=contact_name,
            message_preview=message[:50]
        )

        try:
            # Configurar contexto do pedido para esta conversa
            set_active_conversation(conversation_id)

            # Emit thinking start event
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_start",
            )

            # Executar o grafo do agente
            result = await self.agent_graph.run(
                conversation_id=conversation_id,
                instance_id=instance_id,
                instance_name=instance_name,
                remote_jid=remote_jid,
                contact_name=contact_name,
                message=message,
            )

            response = result.get("response")

            # Emit thinking end event with summary
            intent = result.get("intent", "outro")
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_end",
                data={
                    "summary": f"Intenção: {intent}",
                    "intent": intent,
                },
            )

            if not response:
                logger.warning(
                    "Agent returned no response",
                    conversation_id=conversation_id,
                    intent=result.get("intent")
                )
                return None

            # Enviar resposta via Evolution API
            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=response
            )

            logger.info(
                "Message processed and response sent",
                conversation_id=conversation_id,
                response_length=len(response)
            )

            return response

        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=conversation_id,
                error=str(e)
            )

            # Enviar mensagem de erro genérica
            error_msg = "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente em instantes. 😊"
            await self._send_response(
                instance_name=instance_name,
                remote_jid=remote_jid,
                response=error_msg
            )

            return error_msg

    async def _send_response(
        self,
        instance_name: str,
        remote_jid: str,
        response: str
    ) -> bool:
        """
        Envia a resposta via Evolution API.

        Args:
            instance_name: Nome da instância WhatsApp
            remote_jid: JID do destinatário
            response: Texto da resposta

        Returns:
            True se enviado com sucesso, False caso contrário
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
                instance=instance_name,
                remote_jid=remote_jid
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to send response via Evolution API",
                instance=instance_name,
                remote_jid=remote_jid,
                error=str(e)
            )
            return False

    def get_pedido_atual(self, conversation_id: str) -> list:
        """Retorna o pedido atual de uma conversa."""
        return _pedidos_ativos.get(conversation_id, [])


# Instância singleton do agente
whatsapp_agent = WhatsAppAgent()
