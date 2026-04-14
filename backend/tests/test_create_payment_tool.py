"""
Testes para a ferramenta create_payment_tool.
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.agents.tools.create_payment_tool import create_payment_tool
from app.models.models import PaymentRecord, CustomerOrder, Company, Instance, Contact, Conversation


class TestCreatePaymentTool:
    """Testa a ferramenta de criação de pagamento."""

    def test_create_payment_success(self, db):
        """Testa criação de pagamento com sucesso."""
        # Criar empresa com chave Pix
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
            status="connected",
            company_id=company.id
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
            customer_name="Test Customer",
            total_amount=100.00
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.create_payment_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta
            result = create_payment_tool.invoke({"order_id": order.id})

        # Verificar resultado
        assert "QR Code Pix" in result
        assert "TEST-001" in result
        assert "R$ 100.00" in result

        # Verificar que PaymentRecord foi criado
        payment = db.query(PaymentRecord).filter(PaymentRecord.order_id == order.id).first()
        assert payment is not None
        assert payment.amount == 100.00
        assert payment.status == "pending"
        assert payment.payment_method == "pix"

        # Cleanup
        db.delete(payment)
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(company)
        db.commit()

    def test_create_payment_order_not_found(self, db):
        """Testa erro quando pedido não é encontrado."""
        with patch('app.agents.tools.create_payment_tool.SessionLocal', return_value=db):
            result = create_payment_tool.invoke({"order_id": "non-existent-id"})
        assert "não encontrado" in result.lower()

    def test_create_payment_company_not_found(self, db):
        """Testa erro quando empresa não é encontrada."""
        # Criar pedido sem empresa
        order = CustomerOrder(
            order_number="TEST-002",
            conversation_id="conv-2",
            instance_id="inst-2",
            contact_id="contact-2",
            remote_jid="5511888888888@s.whatsapp.net",
            status="ready_for_confirmation",
            total_amount=50.00
        )
        db.add(order)
        db.commit()

        # Limpar empresas
        db.query(Company).delete()
        db.commit()

        # Chamar a ferramenta
        with patch('app.agents.tools.create_payment_tool.SessionLocal', return_value=db):
            result = create_payment_tool.invoke({"order_id": order.id})

        # Verificar erro
        assert "Empresa não encontrada" in result

        # Cleanup
        db.delete(order)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
