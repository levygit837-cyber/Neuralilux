"""
Output Schemas - Pydantic models para outputs estruturados do agente.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class PedidoItemOutput(BaseModel):
    """Item de um pedido no output."""
    quantidade: int = Field(..., description="Quantidade do item")
    nome: str = Field(..., description="Nome do produto")
    preco_unitario: float = Field(..., description="Preço unitário")
    subtotal: float = Field(..., description="Subtotal (qtd * preço)")
    observacao: Optional[str] = Field(None, description="Observação sobre o item")


class PedidoOutput(BaseModel):
    """Output de comanda de pedido."""
    numero_pedido: Optional[str] = Field(None, description="Número do pedido")
    itens: List[PedidoItemOutput] = Field(..., description="Itens do pedido")
    total: float = Field(..., description="Valor total")
    cliente_nome: Optional[str] = Field(None, description="Nome do cliente")
    cliente_endereco: Optional[str] = Field(None, description="Endereço de entrega")
    cliente_telefone: Optional[str] = Field(None, description="Telefone do cliente")
    forma_pagamento: Optional[str] = Field(None, description="Forma de pagamento")


class VisualizacaoOutput(BaseModel):
    """Output de visualização do pedido atual."""
    itens: List[PedidoItemOutput] = Field(..., description="Itens do pedido")
    total: float = Field(..., description="Valor total")
    quantidade_itens: int = Field(..., description="Quantidade total de itens")


class FinalizacaoOutput(BaseModel):
    """Output de finalização de pedido."""
    numero_pedido: str = Field(..., description="Número do pedido confirmado")
    itens: List[PedidoItemOutput] = Field(..., description="Itens do pedido")
    total: float = Field(..., description="Valor total")
    cliente_nome: str = Field(..., description="Nome do cliente")
    cliente_endereco: str = Field(..., description="Endereço de entrega")
    cliente_telefone: str = Field(..., description="Telefone do cliente")
    forma_pagamento: str = Field(..., description="Forma de pagamento")
    tempo_estimado: Optional[str] = Field("30-45 minutos", description="Tempo estimado de entrega")
    mensagem_confirmacao: Optional[str] = Field(None, description="Mensagem de confirmação")


class ColetaOutput(BaseModel):
    """Output de coleta de informações do cliente."""
    etapa: str = Field(..., description="Etapa atual da coleta")
    mensagem: str = Field(..., description="Mensagem pedindo a informação")
    dados_coletados: Dict[str, Any] = Field(default_factory=dict, description="Dados já coletados")
    proxima_etapa: Optional[str] = Field(None, description="Próxima etapa da coleta")


class MensagemOutput(BaseModel):
    """Output de mensagem simples."""
    mensagem: str = Field(..., description="Mensagem de resposta")
    tipo: str = Field("texto", description="Tipo da mensagem")