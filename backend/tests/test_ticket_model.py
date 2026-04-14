"""
Testes para o modelo Ticket.
"""
import pytest
from sqlalchemy.orm import Session

from app.models.models import Ticket, Conversation, Instance, Contact, User, Company


class TestTicketModel:
    """Testa o modelo Ticket."""

    def test_create_ticket(self, db):
        """Testa criação de um ticket."""
        # Criar empresa
        company = Company(
            name="Test Company",
            is_active=True
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

        # Criar ticket
        ticket = Ticket(
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            agent_type="sac",
            reason="Reclamação de pedido",
            content="Meu pedido chegou errado",
            status="open"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Verificar campos
        assert ticket.id is not None
        assert ticket.conversation_id == conversation.id
        assert ticket.instance_id == instance.id
        assert ticket.contact_id == contact.id
        assert ticket.agent_type == "sac"
        assert ticket.reason == "Reclamação de pedido"
        assert ticket.content == "Meu pedido chegou errado"
        assert ticket.status == "open"
        assert ticket.created_at is not None

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.commit()

    def test_ticket_with_assigned_user(self, db):
        """Testa ticket com usuário atribuído."""
        # Criar usuário
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed_password",
            is_active=True
        )
        db.add(user)
        db.commit()

        # Criar empresa
        company = Company(
            name="Test Company",
            is_active=True
        )
        db.add(company)
        db.commit()

        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-2",
            status="connected",
            company_id=company.id
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

        # Criar ticket com usuário atribuído
        ticket = Ticket(
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            agent_type="sac",
            reason="Test",
            content="Test content",
            status="in_progress",
            assigned_to=user.id
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Verificar atribuição
        assert ticket.assigned_to == user.id
        assert ticket.status == "in_progress"

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(user)
        db.delete(company)
        db.commit()

    def test_ticket_sales_agent_type(self, db):
        """Testa ticket criado por agente Sales."""
        # Criar empresa
        company = Company(
            name="Test Company",
            is_active=True
        )
        db.add(company)
        db.commit()

        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-3",
            status="connected",
            company_id=company.id
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

        # Criar ticket com agent_type sales
        ticket = Ticket(
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            agent_type="sales",
            reason="Dúvida complexa",
            content="Cliente com dúvida sobre pagamento",
            status="open"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Verificar agent_type
        assert ticket.agent_type == "sales"

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(company)
        db.commit()

    def test_ticket_relationships(self, db):
        """Testa relacionamentos do modelo Ticket."""
        # Criar empresa
        company = Company(
            name="Test Company",
            is_active=True
        )
        db.add(company)
        db.commit()

        # Criar instância
        instance = Instance(
            name="Test Instance",
            evolution_instance_id="test-evolution-4",
            status="connected",
            company_id=company.id
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

        # Criar ticket
        ticket = Ticket(
            conversation_id=conversation.id,
            instance_id=instance.id,
            contact_id=contact.id,
            agent_type="sac",
            reason="Test",
            content="Test content"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Verificar relacionamentos
        assert ticket.conversation is not None
        assert ticket.conversation.id == conversation.id
        assert ticket.instance is not None
        assert ticket.instance.id == instance.id
        assert ticket.contact is not None
        assert ticket.contact.id == contact.id

        # Cleanup
        db.delete(ticket)
        db.delete(conversation)
        db.delete(contact)
        db.delete(instance)
        db.delete(company)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
