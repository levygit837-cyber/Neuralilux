"""
Create Payment Tool - Gera QR Code Pix para pagamento.
"""
from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.models import PaymentRecord, CustomerOrder, Company


@tool
def create_payment_tool(order_id: str) -> str:
    """
    Gera QR Code Pix para pagamento de um pedido.
    Use esta ferramenta quando o cliente desejar finalizar um pedido e pagar via Pix.

    Args:
        order_id: ID do pedido a ser pago

    Returns:
        Dados do QR Code Pix e instruções de pagamento.
    """
    db = SessionLocal()
    try:
        # Buscar o pedido
        order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
        if not order:
            return f"Pedido {order_id} não encontrado."

        # Buscar a chave Pix configurada na empresa
        # Assumindo que a chave Pix está armazenada na Company ou em configuração
        # Por enquanto, usaremos um valor padrão que pode ser configurado depois
        company = db.query(Company).first()
        if not company:
            return "Empresa não encontrada para obter chave Pix."

        # Chave Pix - pode ser configurada na Company ou em settings
        # Por enquanto, usando um placeholder
        pix_key = getattr(company, 'pix_key', None) or "00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-4266141740005204000053039865405500.005802BR5913Macedos Delivery6008Fortaleza62070503***63041D3D"

        # Criar PaymentRecord
        payment_record = PaymentRecord(
            order_id=order_id,
            conversation_id=order.conversation_id,
            amount=order.total_amount,
            pix_key=pix_key,
            qr_code_data=pix_key,  # Por enquanto, a chave Pix é o QR Code
            status="pending",
            payment_method="pix"
        )
        db.add(payment_record)
        db.commit()
        db.refresh(payment_record)

        # Formatar resposta
        response = f"""💳 *PAGAMENTO VIA PIX*

━━━━━━━━━━━━━━━━━━━━
📋 *Pedido:* {order.order_number}
💰 *Valor:* R$ {float(order.total_amount):.2f}
━━━━━━━━━━━━━━━━━━━━

📱 *QR Code Pix:*
```
{pix_key}
```

🔑 *Chave Pix:* {pix_key}

━━━━━━━━━━━━━━━━━━━━
⏱️ Este QR Code expira em 15 minutos
💡 Escaneie o QR Code com o app do seu banco para pagar
━━━━━━━━━━━━━━━━━━━━

Após o pagamento, envie o comprovante para confirmarmos."""

        return response

    except Exception as e:
        db.rollback()
        return f"Erro ao gerar pagamento: {str(e)}"
    finally:
        db.close()
