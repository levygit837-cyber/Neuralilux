"""
Agent State - LangGraph state definition for WhatsApp agent.
Defines the shared state that flows through the agent graph.
"""
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.messages import BaseMessage
import operator


# Cache do tipo de agente ativo por conversa
_active_agent_types: Dict[str, str] = {}  # conversation_id -> agent_type


def get_active_agent_type(conversation_id: str) -> str:
    """Retorna o tipo de agente ativo para uma conversa."""
    return _active_agent_types.get(conversation_id, "sales")


def set_active_agent_type(conversation_id: str, agent_type: str):
    """Define o tipo de agente ativo para uma conversa."""
    _active_agent_types[conversation_id] = agent_type


def clear_agent_type_cache(conversation_id: Optional[str] = None):
    """Limpa o cache do tipo de agente. Se conversation_id for None, limpa tudo."""
    if conversation_id:
        _active_agent_types.pop(conversation_id, None)
    else:
        _active_agent_types.clear()


class PedidoItem(TypedDict):
    """Item de um pedido."""
    produto_id: str
    nome: str
    quantidade: int
    preco_unitario: float
    observacao: Optional[str]


class AgentState(TypedDict):
    """
    Estado principal do agente WhatsApp.
    Flui entre os nós do grafo LangGraph.
    """
    # Identificação
    conversation_id: str
    instance_id: str
    instance_name: str
    remote_jid: str
    contact_name: str
    request_id: str

    # Mensagens (histórico LangChain)
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Última mensagem do usuário
    current_message: str
    _history_text: Optional[str]

    # Classificação de intenção
    intent: Optional[str]  # "pedido", "cardapio", "status_pedido", "saudacao", "suporte", "outro"
    intent_confidence: Optional[float]
    flow_stage: Optional[str]  # "saudacao", "explorando_cardapio", "fluxo_comanda", "coletando_dados", "confirmando_pedido", "pedido_finalizado"

    # Tipo de agente ativo
    active_agent_type: Optional[str]  # "sales", "sac"

    # Contexto do cardápio (preenchido pela tool)
    cardapio_context: Optional[str]
    cardapio_items: Optional[List[Dict[str, Any]]]

    # Pedido em andamento (carrinho)
    pedido_atual: Optional[List[PedidoItem]]
    pedido_total: Optional[float]

    # Dados do cliente coletados
    cliente_nome: Optional[str]
    cliente_endereco: Optional[str]
    cliente_telefone: Optional[str]
    forma_pagamento: Optional[str]

    # Estado do fluxo de coleta
    coleta_etapa: Optional[str]  # "nome", "endereco", "telefone", "pagamento", "confirmacao", None

    # Resposta do agente
    response: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]

    # Output estruturado (para formatação)
    output_type: Optional[str]  # "comanda", "visualizacao", "finalizacao", "coleta", "mensagem"
    output_data: Optional[Dict[str, Any]]

    # Metadados
    should_respond: bool
    error: Optional[str]
