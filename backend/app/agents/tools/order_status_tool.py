"""
Order Status Tool - Consulta status do pedido para rastreamento pós-venda.
"""
from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.models import CustomerOrder


@tool
def order_status_tool(order_number: str = None, conversation_id: str = None) -> str:
    """
    Consulta status do pedido no banco de dados para rastreamento pós-venda.
    Use esta ferramenta quando o cliente perguntar pelo status do pedido após o fechamento.

    Args:
        order_number: Número do pedido (opcional, mas recomendado)
        conversation_id: ID da conversa (opcional, usado se order_number não for fornecido)

    Returns:
        Status atual do pedido e informações de rastreamento.
    """
    db = SessionLocal()
    try:
        order = None

        # Tentar buscar por order_number primeiro
        if order_number:
            order = db.query(CustomerOrder).filter(
                CustomerOrder.order_number == order_number
            ).first()
        
        # Se não encontrou por order_number, tentar por conversation_id
        if not order and conversation_id:
            order = db.query(CustomerOrder).filter(
                CustomerOrder.conversation_id == conversation_id
            ).first()

        if not order:
            if order_number:
                return f"Pedido {order_number} não encontrado."
            elif conversation_id:
                return f"Nenhum pedido encontrado para a conversa {conversation_id}."
            else:
                return "Por favor, forneça o número do pedido ou o ID da conversa."

        # Mapear status para português
        status_map = {
            "open": "🟡 Aberto",
            "collecting_data": "🟡 Coletando dados",
            "ready_for_confirmation": "🟡 Pronto para confirmação",
            "closed": "🟢 Fechado",
            "cancelled": "🔴 Cancelado",
            "in_production": "🟠 Em Produção",
            "sent": "🔵 Enviado",
            "delivered": "🟢 Entregue"
        }

        status_display = status_map.get(order.status, f"❓ {order.status}")

        # Formatar resposta
        response = f"""📦 *STATUS DO PEDIDO*

━━━━━━━━━━━━━━━━━━━━
📋 *Pedido:* {order.order_number}
📊 *Status:* {status_display}
💰 *Valor:* R$ {float(order.total_amount):.2f}
━━━━━━━━━━━━━━━━━━━━"""

        # Adicionar informações adicionais baseadas no status
        if order.customer_name:
            response += f"\n👤 *Cliente:* {order.customer_name}"
        
        if order.customer_address:
            response += f"\n📍 *Endereço:* {order.customer_address}"

        if order.opened_at:
            response += f"\n📅 *Aberto em:* {order.opened_at.strftime('%d/%m/%Y %H:%M')}"

        if order.closed_at:
            response += f"\n✅ *Fechado em:* {order.closed_at.strftime('%d/%m/%Y %H:%M')}"

        # Adicionar informações específicas por status
        if order.status == "in_production":
            response += "\n\n⏳ Seu pedido está sendo preparado!"
        elif order.status == "sent":
            response += "\n🚀 Seu pedido saiu para entrega!"
        elif order.status == "delivered":
            response += "\n✅ Seu pedido foi entregue com sucesso!"
        elif order.status == "cancelled":
            response += "\n❌ Este pedido foi cancelado."

        response += "\n━━━━━━━━━━━━━━━━━━━━"

        return response

    except Exception as e:
        return f"Erro ao consultar status do pedido: {str(e)}"
    finally:
        db.close()
