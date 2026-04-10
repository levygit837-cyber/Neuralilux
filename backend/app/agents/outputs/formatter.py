"""
Formatter - Formata outputs estruturados para exibição no WhatsApp.
Converte os outputs Pydantic em texto formatado com emojis.
"""
from typing import Dict, Any

from app.agents.outputs.coleta_output import format_coleta
from app.agents.outputs.finalizacao_output import format_finalizacao
from app.agents.outputs.pedido_output import format_comanda
from app.agents.outputs.visualizacao_output import format_visualizacao


def format_output(output_type: str, data: Dict[str, Any]) -> str:
    """
    Formata um output baseado no tipo.

    Args:
        output_type: Tipo do output (comanda, visualizacao, finalizacao, coleta, mensagem)
        data: Dados do output

    Returns:
        Texto formatado para WhatsApp
    """
    formatters = {
        "comanda": format_comanda,
        "visualizacao": format_visualizacao,
        "finalizacao": format_finalizacao,
        "coleta": format_coleta,
        "mensagem": format_mensagem,
    }

    formatter = formatters.get(output_type, format_mensagem)
    return formatter(data)


def format_mensagem(data: Dict[str, Any]) -> str:
    """Formata mensagem simples."""
    return data.get("mensagem", "")
