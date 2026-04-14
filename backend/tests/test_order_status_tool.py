"""
Testes para a ferramenta order_status_tool.
"""
import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session

from app.agents.tools.order_status_tool import order_status_tool
from app.models.models import CustomerOrder, Conversation, Instance, Contact


class TestOrderStatusTool:
    """Testa a ferramenta de status de pedido."""

    def test_order_status_by_order_number(self, db):
        """Testa consulta de status por número do pedido."""
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
        conversation_id = conversation.id

        # Criar pedido com status de produção
        order = CustomerOrder(
            order_number="TEST-003",
            conversation_id=conversation_id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511777777777@s.whatsapp.net",
            status="in_production",
            customer_name="Test Customer",
            customer_address="Rua Teste, 123",
            total_amount=150.00
        )
        db.add(order)
        db.commit()

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.order_status_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta
            result = order_status_tool.invoke({"order_number": "TEST-003"})

        # Verificar resultado
        assert "STATUS DO PEDIDO" in result
        assert "TEST-003" in result
        assert "Em Produção" in result
        assert "R$ 150.00" in result

        # Cleanup
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_order_status_by_conversation_id(self, db):
        """Testa consulta de status por ID da conversa."""
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
        conversation_id = conversation.id

        # Criar pedido com status enviado
        order = CustomerOrder(
            order_number="TEST-004",
            conversation_id=conversation_id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511666666666@s.whatsapp.net",
            status="sent",
            total_amount=200.00
        )
        db.add(order)
        db.commit()

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.order_status_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta
            result = order_status_tool.invoke({"conversation_id": conversation_id})

        # Verificar resultado
        assert "STATUS DO PEDIDO" in result
        assert "Enviado" in result

        # Cleanup
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_order_status_delivered(self, db):
        """Testa consulta de status entregue."""
        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-5",
            status="connected"
        )
        db.add(instance)
        db.commit()

        # Criar contato
        contact = Contact(
            instance_id=instance.id,
            phone_number="5511555555555",
            remote_jid="5511555555555@s.whatsapp.net",
            name="Test Contact 5"
        )
        db.add(contact)
        db.commit()

        # Criar conversa
        conversation = Conversation(
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511555555555@s.whatsapp.net",
            is_active=True
        )
        db.add(conversation)
        db.commit()
        conversation_id = conversation.id

        # Criar pedido com status entregue
        order = CustomerOrder(
            order_number="TEST-005",
            conversation_id=conversation_id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid="5511555555555@s.whatsapp.net",
            status="delivered",
            total_amount=75.00
        )
        db.add(order)
        db.commit()

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.order_status_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta
            result = order_status_tool.invoke({"order_number": "TEST-005"})

        # Verificar resultado
        assert "STATUS DO PEDIDO" in result
        assert "Entregue" in result
        assert "foi entregue com sucesso" in result.lower()

        # Cleanup
        db.delete(order)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_order_status_not_found(self, db):
        """Testa erro quando pedido não é encontrado."""
        with patch('app.agents.tools.order_status_tool.SessionLocal', return_value=db):
            result = order_status_tool.invoke({"order_number": "NON-EXISTENT"})
        assert "não encontrado" in result.lower()

    def test_order_status_no_parameters(self, db):
        """Testa erro quando não há parâmetros."""
        with patch('app.agents.tools.order_status_tool.SessionLocal', return_value=db):
            result = order_status_tool.invoke({})
        assert "número do pedido" in result.lower() or "conversa" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
