"""
Mensagem Tool - Envio de mensagens via Evolution API.
Permite ao agente enviar respostas de texto para o cliente via WhatsApp.
"""
from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
import structlog

from app.services.evolution_api import EvolutionAPIService
from app.core.database import SessionLocal
from app.models.models import Instance

logger = structlog.get_logger()


@tool
def mensagem_tool(instance_name: str, remote_jid: str, mensagem: str) -> str:
    """
    Envia uma mensagem de texto para o cliente via WhatsApp usando a Evolution API.
    Use esta ferramenta para enviar a resposta final ao cliente.

    Args:
        instance_name: Nome/ID da instância do WhatsApp
        remote_jid: JID do contato WhatsApp (ex: 5511999999999@s.whatsapp.net)
        mensagem: Texto da mensagem a ser enviada

    Returns:
        Confirmação de envio ou erro.
    """
    try:
        evolution = EvolutionAPIService()

        result = evolution.send_text_message(
            instance_name=instance_name,
            remote_jid=remote_jid,
            text=mensagem
        )

        logger.info(
            "Mensagem enviada via agente",
            instance=instance_name,
            remote_jid=remote_jid,
            message_length=len(mensagem)
        )

        return f"Mensagem enviada com sucesso para {remote_jid}."

    except Exception as e:
        logger.error("Erro ao enviar mensagem via agente", error=str(e))
        return f"Erro ao enviar mensagem: {str(e)}"
