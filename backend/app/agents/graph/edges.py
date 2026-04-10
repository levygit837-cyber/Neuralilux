"""
Graph Edges - Condições de transição entre nós do grafo LangGraph.
"""
from typing import Literal
from app.agents.state import AgentState


def should_execute_action(state: AgentState) -> Literal["execute_action", "generate_response"]:
    """
    Decide se deve executar uma ação (tool) antes de gerar a resposta.

    Se a intenção requer consulta ao banco de dados ou manipulação de pedido,
    passa pelo nó de execução de ação primeiro.
    """
    intent = state.get("intent", "outro")

    # Intenções que precisam de ação antes de responder
    action_intents = ["cardapio", "pedido", "status_pedido", "coleta_dados"]

    if intent in action_intents:
        return "execute_action"
    return "generate_response"


def should_respond(state: AgentState) -> Literal["respond", "end"]:
    """
    Decide se o agente deve enviar uma resposta ou encerrar.
    """
    should = state.get("should_respond", True)
    error = state.get("error")

    if error and not state.get("response"):
        # Erro sem resposta - ainda assim responder com mensagem de erro
        return "respond"

    if should:
        return "respond"
    return "end"