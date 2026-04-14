"""
Testes para a ferramenta open_ticket_tool.
"""
import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session

from app.agents.tools.open_ticket_tool import open_ticket_with_context
from app.models.models import Ticket, Conversation, Instance, Contact, User


class TestOpenTicketTool:
    """Testa a ferramenta de abertura de tickets."""

    def test_open_ticket_success(self, db):
        """Testa abertura de ticket com sucesso."""
        # Criar usuário para atribuição
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed_password",
            is_active=True
        )
        db.add(user)
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
        conversation_id = conversation.id

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.open_ticket_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta
            result = open_ticket_with_context.invoke({
                "conversation_id": conversation_id,
                "instance_id": instance.id,
                "contact_id": contact.id,
                "agent_type": "sac",
                "reason": "Reclamação de pedido",
                "content": "Meu pedido chegou errado"
            })

        # Verificar resultado
        assert "TICKET CRIADO" in result
        assert "Reclamação de pedido" in result

        # Verificar que Ticket foi criado
        ticket = db.query(Ticket).filter(Ticket.conversation_id == conversation_id).first()
        assert ticket is not None
        assert ticket.reason == "Reclamação de pedido"
        assert ticket.content == "Meu pedido chegou errado"
        assert ticket.agent_type == "sac"
        assert ticket.status == "open"

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(user)
        db.commit()

    def test_open_ticket_conversation_not_found(self, db):
        """Testa erro quando conversa não é encontrada."""
        with patch('app.agents.tools.open_ticket_tool.SessionLocal', return_value=db):
            result = open_ticket_with_context.invoke({
                "conversation_id": "non-existent-id",
                "instance_id": "inst-1",
                "contact_id": "contact-1",
                "agent_type": "sac",
                "reason": "Test",
                "content": "Test content"
            })

        assert "não encontrada" in result.lower()

    def test_open_ticket_with_sales_agent_type(self, db):
        """Testa abertura de ticket por agente Sales."""
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
        conversation_id = conversation.id

        # Usar monkeypatch para substituir SessionLocal
        with patch('app.agents.tools.open_ticket_tool.SessionLocal', return_value=db):
            # Chamar a ferramenta com agent_type sales
            result = open_ticket_with_context.invoke({
                "conversation_id": conversation_id,
                "instance_id": instance.id,
                "contact_id": contact.id,
                "agent_type": "sales",
                "reason": "Dúvida complexa",
                "content": "Cliente com dúvida sobre pagamento"
            })

        # Verificar resultado
        assert "TICKET CRIADO" in result

        # Verificar que Ticket foi criado com agent_type correto
        ticket = db.query(Ticket).filter(Ticket.conversation_id == conversation_id).first()
        assert ticket is not None
        assert ticket.agent_type == "sales"

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
