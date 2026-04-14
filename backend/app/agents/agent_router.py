"""
Agent Router - Gerencia transição automática entre tipos de agentes.
Analisa a intenção da mensagem e determina qual agente deve atender.
"""
from typing import Dict, Any, Optional
import structlog
from app.agents.state import get_active_agent_type, set_active_agent_type
from app.core.database import SessionLocal
from app.models.models import Conversation

logger = structlog.get_logger()


# Palavras-chave que indicam necessidade de SAC
SAC_KEYWORDS = [
    "reclamação", "reclamar", "problema", "erro", "erro no pedido",
    "atraso", "demorou", "não chegou", "pedido errado", "item errado",
    "cancelar pedido", "devolução", "reembolso", "insatisfeito",
    "queixa", "denúncia", "suporte", "ajuda técnica", "defeito",
    "estragou", "estragado", "veio errado", "não veio", "faltou"
]

# Palavras-chave que indicam retorno para Vendas
SALES_KEYWORDS = [
    "pedido", "quer pedir", "gostaria de pedir", "fazer pedido",
    "cardápio", "menu", "preço", "valor", "quanto custa",
    "quero", "gostaria", "vou levar", "adicionar", "comprar"
]


def classify_agent_type(message: str, current_agent_type: str) -> str:
    """
    Classifica qual tipo de agente deve atender baseado na mensagem.
    
    Args:
        message: Mensagem do cliente
        current_agent_type: Tipo de agente atual ("sales" ou "sac")
        
    Returns:
        Tipo de agente que deve atender ("sales" ou "sac")
    """
    message_lower = message.lower().strip()
    
    # Se já está no SAC, verificar se deve voltar para Vendas
    if current_agent_type == "sac":
        for keyword in SALES_KEYWORDS:
            if keyword in message_lower:
                logger.info(
                    "Transition detected: SAC -> Sales",
                    keyword=keyword,
                    message_preview=message[:50]
                )
                return "sales"
        
        # Permanece no SAC
        return "sac"
    
    # Se está em Vendas, verificar se deve ir para SAC
    if current_agent_type == "sales":
        for keyword in SAC_KEYWORDS:
            if keyword in message_lower:
                logger.info(
                    "Transition detected: Sales -> SAC",
                    keyword=keyword,
                    message_preview=message[:50]
                )
                return "sac"
        
        # Permanece em Vendas
        return "sales"
    
    # Padrão: Vendas
    return "sales"


def route_agent(
    conversation_id: str,
    message: str,
    conversation_db: Optional[Conversation] = None
) -> Dict[str, Any]:
    """
    Roteia a mensagem para o agente apropriado.
    
    Args:
        conversation_id: ID da conversa
        message: Mensagem do cliente
        conversation_db: Objeto Conversation do banco (opcional, para evitar query extra)
        
    Returns:
        Dicionário com:
        - agent_type: tipo de agente que deve atender
        - transition_occurred: se houve transição
        - previous_agent_type: tipo anterior (se houve transição)
    """
    # Obter tipo atual do cache
    current_agent_type = get_active_agent_type(conversation_id)
    
    # Se não estiver no cache, buscar do banco
    if current_agent_type == "sales" and conversation_db:
        current_agent_type = conversation_db.active_agent_type or "sales"
    
    # Classificar tipo de agente baseado na mensagem
    new_agent_type = classify_agent_type(message, current_agent_type)
    
    # Verificar se houve transição
    transition_occurred = new_agent_type != current_agent_type
    
    if transition_occurred:
        logger.info(
            "Agent type transition",
            conversation_id=conversation_id,
            previous=current_agent_type,
            new=new_agent_type,
            message_preview=message[:100]
        )
        
        # Atualizar cache
        set_active_agent_type(conversation_id, new_agent_type)
        
        # Atualizar banco de dados
        try:
            db = SessionLocal()
            try:
                conversation = conversation_db or db.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if conversation:
                    conversation.active_agent_type = new_agent_type
                    db.commit()
                    logger.info(
                        "Updated conversation agent_type in DB",
                        conversation_id=conversation_id,
                        agent_type=new_agent_type
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error(
                "Failed to update conversation agent_type in DB",
                conversation_id=conversation_id,
                error=str(e)
            )
    
    return {
        "agent_type": new_agent_type,
        "transition_occurred": transition_occurred,
        "previous_agent_type": current_agent_type if transition_occurred else None
    }


def should_use_delivery_tool(message: str) -> bool:
    """
    Verifica se a mensagem deve usar a ferramenta de entrega.
    
    Args:
        message: Mensagem do cliente
        
    Returns:
        True se deve usar delivery_tool, False caso contrário
    """
    message_lower = message.lower().strip()
    
    delivery_keywords = [
        "entrega", "taxa de entrega", "frete", "bairro",
        "quanto custa a entrega", "entrega no meu bairro",
        "vocês entregam", "taxa", "valor da entrega"
    ]
    
    for keyword in delivery_keywords:
        if keyword in message_lower:
            return True
    
    return False
