"""
Outputs - Structured output formatting for the WhatsApp agent.
"""
from app.agents.outputs.schemas import (
    PedidoOutput,
    VisualizacaoOutput,
    FinalizacaoOutput,
    ColetaOutput,
)
from app.agents.outputs.formatter import format_output
from app.agents.outputs.pedido_output import format_comanda
from app.agents.outputs.visualizacao_output import format_visualizacao
from app.agents.outputs.finalizacao_output import format_finalizacao
from app.agents.outputs.coleta_output import format_coleta

__all__ = [
    "PedidoOutput",
    "VisualizacaoOutput",
    "FinalizacaoOutput",
    "ColetaOutput",
    "format_output",
    "format_comanda",
    "format_visualizacao",
    "format_finalizacao",
    "format_coleta",
]