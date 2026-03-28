"""
History Loader - Carrega histórico de mensagens do banco de dados.
Converte mensagens do DB para o formato LangChain para uso no agente.
"""
from typing import List, Dict, Any, Optional

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import structlog

from app.core.database import SessionLocal
from app.models.models import Message, Conversation

logger = structlog.get_logger()


def load_conversation_history(
    conversation_id: str,
    limit: int = 20
) -> List[Dict[str, str]]:
    """
    Carrega o histórico de mensagens de uma conversa do banco de dados.

    Args:
        conversation_id: ID da conversa
        limit: Número máximo de mensagens a carregar

    Returns:
        Lista de dicionários no formato {"role": "user/assistant", "content": "..."}
    """
    db = SessionLocal()
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(
            Message.timestamp.desc()
        ).limit(limit).all()

        # Inverter para ordem cronológica
        messages = list(reversed(messages))

        history = []
        for msg in messages:
            role = "user" if msg.direction == "incoming" else "assistant"
            content = msg.content or ""
            if content and content not in ["[Mensagem]", "[Áudio]"]:
                history.append({
                    "role": role,
                    "content": content
                })

        return history

    except Exception as e:
        logger.error("Error loading conversation history", error=str(e))
        return []
    finally:
        db.close()


def load_conversation_history_as_langchain(
    conversation_id: str,
    limit: int = 20
) -> List[Any]:
    """
    Carrega o histórico de mensagens no formato LangChain.

    Args:
        conversation_id: ID da conversa
        limit: Número máximo de mensagens

    Returns:
        Lista de mensagens LangChain (HumanMessage, AIMessage)
    """
    history_dicts = load_conversation_history(conversation_id, limit)

    messages = []
    for msg in history_dicts:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    return messages


def get_conversation_info(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém informações básicas da conversa.

    Args:
        conversation_id: ID da conversa

    Returns:
        Dicionário com informações da conversa ou None
    """
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        return {
            "id": str(conversation.id),
            "instance_id": str(conversation.instance_id),
            "contact_id": str(conversation.contact_id),
            "remote_jid": conversation.remote_jid,
            "is_active": conversation.is_active,
            "assigned_agent_id": str(conversation.assigned_agent_id) if conversation.assigned_agent_id else None,
        }

    except Exception as e:
        logger.error("Error getting conversation info", error=str(e))
        return None
    finally:
        db.close()


def get_contact_info(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém informações do contato da conversa.

    Args:
        conversation_id: ID da conversa

    Returns:
        Dicionário com informações do contato ou None
    """
    from app.models.models import Contact

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        contact = db.query(Contact).filter(
            Contact.id == conversation.contact_id
        ).first()

        if not contact:
            return None

        return {
            "id": str(contact.id),
            "name": contact.name or contact.push_name or contact.phone_number,
            "phone_number": contact.phone_number,
            "remote_jid": contact.remote_jid,
            "profile_pic_url": contact.profile_pic_url,
        }

    except Exception as e:
        logger.error("Error getting contact info", error=str(e))
        return None
    finally:
        db.close()
