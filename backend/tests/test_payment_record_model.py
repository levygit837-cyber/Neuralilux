"""
Testes para o modelo PaymentRecord.
"""
import pytest
from sqlalchemy.orm import Session

from app.models.models import PaymentRecord, CustomerOrder, Conversation, Instance, Contact, Company


class TestPaymentRecordModel:
    """Testa o modelo PaymentRecord."""

    def test_create_payment_record(self, db):
        """Testa criação de um PaymentRecord."""
        # Criar empresa
        company = Company(
            name="Test Company",
            pix_key="00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-426614174000"
        )
        db.add(company)
        db.commit()

        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution",
            status="connected"
        )
        db.add(instance)
        db.commit()

        # Criar contato
        contact = Contact(
            instance_id=instance.id,
            phone_number="5511999999999",
            remote_jid="5511999999999@s.whatsapp.net",
            name="Test Contact"
        )
        db.add(contact)
        db.commit()

        # Criar conversa
        conversation = Conversation(
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511999999999@s.whatsapp.net",
            is_active=True
        )
        db.add(conversation)
        db.commit()

        # Criar pedido
        order = CustomerOrder(
            order_number="TEST-001",
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511999999999@s.whatsapp.net",
            status="ready_for_confirmation",
            total_amount=100.00
        )
        db.add(order)
        db.commit()

        # Criar PaymentRecord
        payment = PaymentRecord(
            order_id=order.id,
            conversation_id=conversation.id,
            amount=100.00,
            pix_key="00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-426614174000",
            qr_code_data="QR_CODE_DATA",
            status="pending",
            payment_method="pix"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Verificar campos
        assert payment.id is not None
        assert payment.order_id == order.id
        assert payment.conversation_id == conversation.id
        assert payment.amount == 100.00
        assert payment.pix_key == "00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-426614174000"
        assert payment.qr_code_data == "QR_CODE_DATA"
        assert payment.status == "pending"
        assert payment.payment_method == "pix"
        assert payment.created_at is not None
        assert payment.paid_at is None

        # Cleanup
        db.delete(payment)
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(company)
        db.commit()

    def test_payment_record_paid_status(self, db):
        """Testa PaymentRecord com status pago."""
        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-2",
            status="connected"
        )
        db.add(instance)
        db.commit()

        # Criar contato
        contact = Contact(
            instance_id=instance.id,
            phone_number="5511888888888",
            remote_jid="5511888888888@s.whatsapp.net",
            name="Test Contact 2"
        )
        db.add(contact)
        db.commit()

        # Criar conversa
        conversation = Conversation(
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511888888888@s.whatsapp.net",
            is_active=True
        )
        db.add(conversation)
        db.commit()

        # Criar pedido
        order = CustomerOrder(
            order_number="TEST-002",
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511888888888@s.whatsapp.net",
            status="closed",
            total_amount=50.00
        )
        db.add(order)
        db.commit()

        # Criar PaymentRecord com status paid
        from datetime import datetime, timezone
        payment = PaymentRecord(
            order_id=order.id,
            conversation_id=conversation.id,
            amount=50.00,
            pix_key="PIX_KEY",
            qr_code_data="QR_CODE",
            status="paid",
            payment_method="pix",
            paid_at=datetime.now(timezone.utc)
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Verificar status pago
        assert payment.status == "paid"
        assert payment.paid_at is not None

        # Cleanup
        db.delete(payment)
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_payment_record_relationships(self, db):
        """Testa relacionamentos do modelo PaymentRecord."""
        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-3",
            status="connected"
        )
        db.add(instance)
        db.commit()

        # Criar contato
        contact = Contact(
            instance_id=instance.id,
            phone_number="5511777777777",
            remote_jid="5511777777777@s.whatsapp.net",
            name="Test Contact 3"
        )
        db.add(contact)
        db.commit()

        # Criar conversa
        conversation = Conversation(
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511777777777@s.whatsapp.net",
            is_active=True
        )
        db.add(conversation)
        db.commit()

        # Criar pedido
        order = CustomerOrder(
            order_number="TEST-003",
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511777777777@s.whatsapp.net",
            status="ready_for_confirmation",
            total_amount=75.00
        )
        db.add(order)
        db.commit()

        # Criar PaymentRecord
        payment = PaymentRecord(
            order_id=order.id,
            conversation_id=conversation.id,
            amount=75.00,
            pix_key="PIX_KEY",
            qr_code_data="QR_DATA",
            status="pending",
            payment_method="pix"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Verificar relacionamentos
        assert payment.order is not None
        assert payment.order.id == order.id
        assert payment.conversation is not None
        assert payment.conversation.id == conversation.id

        # Cleanup
        db.delete(payment)
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_payment_record_expired_status(self, db):
        """Testa PaymentRecord com status expirado."""
        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-4",
            status="connected"
        )
        db.add(instance)
        db.commit()

        # Criar contato
        contact = Contact(
            instance_id=instance.id,
            phone_number="5511666666666",
            remote_jid="5511666666666@s.whatsapp.net",
            name="Test Contact 4"
        )
        db.add(contact)
        db.commit()

        # Criar conversa
        conversation = Conversation(
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511666666666@s.whatsapp.net",
            is_active=True
        )
        db.add(conversation)
        db.commit()

        # Criar pedido
        order = CustomerOrder(
            order_number="TEST-004",
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511666666666@s.whatsapp.net",
            status="cancelled",
            total_amount=25.00
        )
        db.add(order)
        db.commit()

        # Criar PaymentRecord com status expired
        payment = PaymentRecord(
            order_id=order.id,
            conversation_id=conversation.id,
            amount=25.00,
            pix_key="PIX_KEY",
            qr_code_data="QR_DATA",
            status="expired",
            payment_method="pix"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Verificar status expirado
        assert payment.status == "expired"

        # Cleanup
        db.delete(payment)
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
