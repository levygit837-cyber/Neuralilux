"""
Open Ticket Tool - Abre ticket para atendente humano.
"""
from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.models import Ticket, Conversation, Instance, Contact


@tool
def open_ticket_tool(reason: str, content: str) -> str:
    """
    Abre um ticket para chamar um atendente humano.
    Use esta ferramenta quando o cliente precisar de atendimento humano ou quando não for possível resolver automaticamente.

    Args:
        reason: Motivo do ticket (ex: "Reclamação", "Problema técnico", "Dúvida complexa")
        content: Conteúdo detalhado da reclamação ou mensagem do usuário

    Returns:
        Confirmação da criação do ticket e número de referência.
    """
    # Nota: Esta ferramenta precisa ser chamada com contexto da conversa
    # O conversation_id, instance_id e contact_id devem ser obtidos do estado do agente
    # Por enquanto, vamos assumir que esses valores são passados via contexto global ou precisam ser adicionados como parâmetros
    
    # Para funcionar corretamente, precisamos adicionar parâmetros de contexto
    # Vou adicionar uma versão simplificada que pode ser expandida depois
    
    return "Para abrir um ticket, por favor forneça o conversation_id, instance_id e contact_id junto com reason e content. Esta ferramenta precisa de contexto adicional para funcionar corretamente."


@tool
def open_ticket_with_context(conversation_id: str, instance_id: str, contact_id: str, agent_type: str, reason: str, content: str) -> str:
    """
    Abre um ticket para chamar um atendente humano com contexto completo.
    Use esta ferramenta quando o cliente precisar de atendimento humano.

    Args:
        conversation_id: ID da conversa
        instance_id: ID da instância WhatsApp
        contact_id: ID do contato
        agent_type: Tipo de agente que está criando o ticket ("sales" ou "sac")
        reason: Motivo do ticket (ex: "Reclamação", "Problema técnico", "Dúvida complexa")
        content: Conteúdo detalhado da reclamação ou mensagem do usuário

    Returns:
        Confirmação da criação do ticket e número de referência.
    """
    db = SessionLocal()
    try:
        # Validar que a conversa existe
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return f"Conversa {conversation_id} não encontrada."

        # Criar Ticket
        ticket = Ticket(
            conversation_id=conversation_id,
            instance_id=instance_id,
            contact_id=contact_id,
            agent_type=agent_type,
            reason=reason,
            content=content,
            status="open"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Formatar resposta
        response = f"""🎫 *TICKET CRIADO*

━━━━━━━━━━━━━━━━━━━━
📋 *Ticket ID:* {ticket.id[:8].upper()}
🏷️ *Motivo:* {reason}
📅 *Data:* {ticket.created_at.strftime('%d/%m/%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━

✅ Seu ticket foi aberto com sucesso!
👨‍💻 Um atendente humano entrará em contato em breve.

💡 *Número de referência:* {ticket.id}

━━━━━━━━━━━━━━━━━━━━
O atendimento automático foi pausado. Aguarde o contato de nosso atendente.
━━━━━━━━━━━━━━━━━━━━"""

        return response

    except Exception as e:
        db.rollback()
        return f"Erro ao abrir ticket: {str(e)}"
    finally:
        db.close()
