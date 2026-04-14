"""
Delivery Tool - Cálculo de taxas de entrega baseado em bairro/região.
"""
from typing import Any, Dict
from langchain_core.tools import tool

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312
from app.core.database import SessionLocal
from app.services.delivery_zone_service import (
    get_delivery_fee,
    list_active_zones,
    get_all_neighborhoods,
    NeighborhoodNotFoundError,
    NoActiveZonesError,
    DeliveryZoneServiceError,
)

patch_forward_ref_evaluate_for_python312()

_current_conversation_id: str = "default"


def set_active_conversation(conversation_id: str):
    global _current_conversation_id
    _current_conversation_id = conversation_id


def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@tool
def delivery_tool(
    acao: str,
    bairro: str = "",
    valor_pedido: float = 0,
) -> str:
    """
    Consulta e calcula taxas de entrega baseadas em bairro/região.

    Ações disponíveis:
    - consultar_taxa: Calcula a taxa para um bairro específico
    - listar_regioes: Lista todas as zonas de entrega ativas
    - listar_bairros: Lista todos os bairros atendidos

    Parâmetros:
    - acao: Ação a executar (consultar_taxa, listar_regioes, listar_bairros)
    - bairro: Nome do bairro (obrigatório para consultar_taxa)
    - valor_pedido: Valor total do pedido (opcional, para verificar valor mínimo)
    """
    db = SessionLocal()
    try:
        acao_lower = acao.lower().strip()

        if acao_lower == "consultar_taxa":
            return _consultar_taxa(db, bairro, valor_pedido)
        
        if acao_lower == "listar_regioes":
            return _listar_regioes(db)
        
        if acao_lower == "listar_bairros":
            return _listar_bairros(db)

        return "Ação inválida. Use: consultar_taxa, listar_regioes ou listar_bairros."
    finally:
        db.close()


def _consultar_taxa(db, bairro: str, valor_pedido: float) -> str:
    """Consulta a taxa de entrega para um bairro específico."""
    if not bairro:
        return "Por favor, informe o nome do bairro para consultar a taxa de entrega."
    
    try:
        result = get_delivery_fee(db, bairro, valor_pedido)
        
        response = f"📍 Taxa de entrega para {result['neighborhood']}:\n"
        response += f"🚚 Zona: {result['zone_name']}\n"
        response += f"💰 Taxa: {_formatar_preco(result['fee'])}\n"
        
        if result['minimum_order_value'] > 0:
            response += f"📦 Valor mínimo: {_formatar_preco(result['minimum_order_value'])}\n"
            if result['meets_minimum']:
                response += f"✅ Seu pedido atende o valor mínimo.\n"
            else:
                falta = result['minimum_order_value'] - valor_pedido
                response += f"⚠️ Faltam {_formatar_preco(falta)} para atingir o valor mínimo.\n"
        
        return response
    except NeighborhoodNotFoundError:
        return f"❌ Bairro '{bairro}' não encontrado em nossa zona de entrega. Por favor, verifique o nome ou entre em contato para confirmar se entregamos na sua região."
    except NoActiveZonesError:
        return "❌ Não há zonas de entrega configuradas no momento. Por favor, entre em contato conosco."
    except DeliveryZoneServiceError as e:
        return f"❌ Erro ao consultar taxa de entrega: {str(e)}"


def _listar_regioes(db) -> str:
    """Lista todas as zonas de entrega ativas."""
    try:
        zones = list_active_zones(db)
        
        response = "📍 Zonas de Entrega Disponíveis:\n"
        response += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for zone in zones:
            response += f"🚚 {zone['name']}\n"
            response += f"   💰 Taxa: {_formatar_preco(zone['delivery_fee'])}\n"
            if zone['minimum_order_value'] > 0:
                response += f"   📦 Mínimo: {_formatar_preco(zone['minimum_order_value'])}\n"
            
            # Listar bairros
            if zone['neighborhoods']:
                bairros = zone['neighborhoods'][:5]  # Mostrar até 5 bairros
                response += f"   📍 Bairros: {', '.join(bairros)}"
                if len(zone['neighborhoods']) > 5:
                    response += f" e mais {len(zone['neighborhoods']) - 5}..."
                response += "\n"
            
            response += "\n"
        
        response += "━━━━━━━━━━━━━━━━━━━━\n"
        response += "💡 Digite o nome do seu bairro para consultar a taxa específica."
        
        return response
    except NoActiveZonesError:
        return "❌ Não há zonas de entrega configuradas no momento."
    except DeliveryZoneServiceError as e:
        return f"❌ Erro ao listar zonas de entrega: {str(e)}"


def _listar_bairros(db) -> str:
    """Lista todos os bairros atendidos."""
    try:
        bairros = get_all_neighborhoods(db)
        
        if not bairros:
            return "❌ Não há bairros cadastrados no momento."
        
        response = "📍 Bairros Atendidos:\n"
        response += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Agrupar por letras para facilitar leitura
        bairros_sorted = sorted(bairros)
        for i, bairro in enumerate(bairros_sorted):
            response += f"• {bairro}\n"
        
        response += "\n━━━━━━━━━━━━━━━━━━━━\n"
        response += f"Total: {len(bairros)} bairros atendidos.\n"
        response += "💡 Digite o nome do seu bairro para consultar a taxa."
        
        return response
    except DeliveryZoneServiceError as e:
        return f"❌ Erro ao listar bairros: {str(e)}"
