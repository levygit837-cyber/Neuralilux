"""
Agent Tools - Tools available to the WhatsApp agent.
"""
from app.agents.tools.cardapio_tool import cardapio_tool
from app.agents.tools.pedido_tool import pedido_tool
from app.agents.tools.mensagem_tool import mensagem_tool
from app.agents.tools.horario_tool import horario_tool

ALL_TOOLS = [cardapio_tool, pedido_tool, mensagem_tool, horario_tool]

__all__ = ["cardapio_tool", "pedido_tool", "mensagem_tool", "horario_tool", "ALL_TOOLS"]