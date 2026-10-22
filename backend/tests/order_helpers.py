"""Orders prontos para os testes do painel (#34): API, concorrência e aviso ao Contact."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models import Contact, Conversation, CustomerOrder, CustomerOrderItem, PaymentRecord

NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)


def make_order(db, instance, number, status="closed", *, confirmed=True, pix=None, opened_at=NOW, conversation=None):
    """Order de 2 Pizza Toscana (total 95). Sem `conversation`, cria Contact e Conversation próprios."""
    if conversation is None:
        contact = Contact(instance_id=instance.id, phone_number=f"55{number}", remote_jid=f"{number}@s.whatsapp.net", name="Maria")
        db.add(contact)
        db.flush()
        conversation = Conversation(instance_id=instance.id, contact_id=contact.id, remote_jid=contact.remote_jid)
        db.add(conversation)
        db.flush()
    order = CustomerOrder(
        order_number=number, conversation_id=conversation.id, instance_id=instance.id, contact_id=conversation.contact_id,
        remote_jid=conversation.remote_jid, status=status, total_amount=Decimal("95.00"), delivery_fee=Decimal("5.00"),
        customer_name="Maria", payment_method="pix" if pix else "dinheiro", delivery_type="entrega",
        opened_at=opened_at, closed_at=opened_at if confirmed else None,
    )
    db.add(order)
    db.flush()
    db.add(CustomerOrderItem(
        order_id=order.id, item_name="Pizza Toscana", quantity=2, unit_price=Decimal("45.00"), subtotal_price=Decimal("90.00"),
    ))
    if pix:
        db.add(PaymentRecord(
            order_id=order.id, conversation_id=conversation.id, amount=Decimal("95.00"), pix_key="k@pix",
            payment_method="pix", status=pix,
        ))
    db.commit()
    return order
