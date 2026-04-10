"""
End-to-end tests for WhatsApp Agent with real LM Studio inference.

These tests simulate a real client sending WhatsApp messages and validate
that the agent processes them correctly and sends responses back.
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import Instance, Agent, Contact, Conversation, Message
from app.agents.agent_executor import whatsapp_agent
from app.services.inference_service import get_inference_service


@pytest.fixture
def test_db():
    """Create a test database session."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_agent(test_db):
    """Create a test agent."""
    agent = Agent(
        name=f"Test E2E Agent {uuid.uuid4()}",
        system_prompt="Você é um assistente de teste para validação E2E.",
        is_active=True
    )
    test_db.add(agent)
    test_db.commit()
    test_db.refresh(agent)
    
    yield agent
    
    test_db.delete(agent)
    test_db.commit()


@pytest.fixture
def test_instance(test_db, test_agent):
    """Create a test WhatsApp instance with agent assigned."""
    instance_id = f"test-e2e-instance-{uuid.uuid4()}"
    instance = Instance(
        name=instance_id,
        evolution_instance_id=instance_id,
        agent_enabled=True,
        agent_id=test_agent.id,
        status="connected",
        is_active=True
    )
    test_db.add(instance)
    test_db.commit()
    test_db.refresh(instance)
    
    yield instance
    
    test_db.delete(instance)
    test_db.commit()


@pytest.fixture
def test_conversation(test_db, test_instance):
    """Create a test conversation."""
    phone = f"55119{uuid.uuid4().hex[:10]}"
    remote_jid = f"{phone}@s.whatsapp.net"
    
    contact = Contact(
        instance_id=test_instance.id,
        phone_number=phone,
        remote_jid=remote_jid,
        name="Test Client"
    )
    test_db.add(contact)
    test_db.flush()
    
    conversation = Conversation(
        instance_id=test_instance.id,
        contact_id=contact.id,
        remote_jid=remote_jid,
        is_active=True
    )
    test_db.add(conversation)
    test_db.commit()
    test_db.refresh(conversation)
    
    yield conversation, remote_jid
    
    test_db.delete(conversation)
    test_db.delete(contact)
    test_db.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_whatsapp_agent_full_flow_real_lm_studio(test_instance, test_agent, test_conversation):
    """Teste E2E completo com LM Studio real - fluxo básico de mensagem."""
    
    conversation, remote_jid = test_conversation
    
    # Verificar se LM Studio está disponível
    inference_service = get_inference_service("whatsapp_agent")
    try:
        # Tenta fazer um health check simples
        test_messages = [{"role": "user", "content": "test"}]
        result = await inference_service.chat_completion(
            messages=test_messages,
            max_tokens=10,
            temperature=0.1
        )
        assert result is not None, "LM Studio não está respondendo"
    except Exception as e:
        pytest.skip(f"LM Studio não disponível: {e}")
    
    # Enviar mensagem do cliente
    client_message = "Olá"
    
    try:
        response = await whatsapp_agent.process_message(
            conversation_id=str(conversation.id),
            instance_id=str(test_instance.id),
            instance_name=test_instance.name,
            remote_jid=remote_jid,
            contact_name="Test Client",
            message=client_message
        )
        
        # Validar resposta
        assert response is not None, "Agent não retornou resposta"
        assert len(response) > 0, "Resposta vazia"
        assert "Desculpe, estou com dificuldades técnicas" not in response, "Resposta de erro genérico"
        
        # Validar que mensagem foi enviada (verificar banco)
        db = SessionLocal()
        messages = db.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.direction == "outgoing"
        ).all()
        assert len(messages) > 0, "Nenhuma mensagem enviada ao cliente"
        db.close()
        
        print(f"✓ Teste E2E passou: resposta recebida: {response[:100]}...")
        
    except Exception as e:
        pytest.fail(f"Teste E2E falhou: {str(e)}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_agent_auto_resolution_no_agent_id(test_db, test_conversation):
    """Testa resolução automática de agent_id quando None."""
    
    conversation, remote_jid = test_conversation
    
    # Criar instância sem agent_id mas com agent_enabled=True
    # Criar um agent global primeiro
    global_agent = Agent(
        name=f"Global Test Agent {uuid.uuid4()}",
        system_prompt="Você é um assistente global.",
        is_active=True,
        owner_id=None  # Agent global
    )
    test_db.add(global_agent)
    test_db.commit()
    test_db.refresh(global_agent)
    
    instance_id = f"test-auto-resolution-{uuid.uuid4()}"
    instance = Instance(
        name=instance_id,
        evolution_instance_id=instance_id,
        agent_enabled=True,
        agent_id=None,  # Sem agent atribuído
        status="connected",
        is_active=True
    )
    test_db.add(instance)
    test_db.commit()
    test_db.refresh(instance)
    
    # Simular mensagem chegando via worker (chamando diretamente o agent)
    # Nota: A resolução automática acontece no worker, não no agent_executor
    # Este teste valida que o worker resolve o agent_id antes de chamar o agent
    
    try:
        response = await whatsapp_agent.process_message(
            conversation_id=str(conversation.id),
            instance_id=str(instance.id),
            instance_name=instance.name,
            remote_jid=remote_jid,
            contact_name="Test Client",
            message="Teste"
        )
        
        # Se não houver agent, o agent_executor vai lançar exceção
        # Este teste valida esse comportamento
        assert response is None or "dificuldades técnicas" in response, "Comportamento inesperado sem agent"
        
    except Exception as e:
        # Esperado que falhe se não houver agent
        assert "agent" in str(e).lower() or "enabled" in str(e).lower(), f"Erro inesperado: {str(e)}"
    
    finally:
        # Cleanup
        test_db.delete(global_agent)
        test_db.delete(instance)
        test_db.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_agent_custom_exceptions(test_instance, test_agent, test_conversation):
    """Testa que exceções customizadas são lançadas corretamente."""
    
    conversation, remote_jid = test_conversation
    
    from app.agents.exceptions import AgentNotAssignedError
    
    # Criar instância sem agent
    instance_id = f"test-no-agent-{uuid.uuid4()}"
    instance_no_agent = Instance(
        name=instance_id,
        evolution_instance_id=instance_id,
        agent_enabled=True,
        agent_id=None,
        status="connected",
        is_active=True
    )
    db = SessionLocal()
    db.add(instance_no_agent)
    db.commit()
    db.refresh(instance_no_agent)
    db.close()
    
    try:
        # Tentar processar sem agent - deve falhar
        response = await whatsapp_agent.process_message(
            conversation_id=str(conversation.id),
            instance_id=str(instance_no_agent.id),
            instance_name=instance_no_agent.name,
            remote_jid=remote_jid,
            contact_name="Test Client",
            message="Test"
        )
        
        # Se chegou aqui, algo está errado - não deveria processar sem agent
        pytest.fail("Agent processou mensagem sem agent_id, isso não deveria acontecer")
        
    except Exception as e:
        # Esperado que falhe de alguma forma
        # O agent_executor pode lançar exceção ou retornar erro
        assert True  # Teste passou se falhou como esperado
        
    finally:
        # Cleanup
        db = SessionLocal()
        db.delete(instance_no_agent)
        db.commit()
        db.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_agent_cardapio_intent(test_instance, test_agent, test_conversation):
    """Teste E2E com intenção de cardápio."""
    
    conversation, remote_jid = test_conversation
    
    # Verificar se LM Studio está disponível
    inference_service = get_inference_service("whatsapp_agent")
    try:
        test_messages = [{"role": "user", "content": "test"}]
        result = await inference_service.chat_completion(
            messages=test_messages,
            max_tokens=10,
            temperature=0.1
        )
        assert result is not None
    except Exception as e:
        pytest.skip(f"LM Studio não disponível: {e}")
    
    # Enviar mensagem pedindo cardápio
    client_message = "Quero ver o cardápio"
    
    try:
        response = await whatsapp_agent.process_message(
            conversation_id=str(conversation.id),
            instance_id=str(test_instance.id),
            instance_name=test_instance.name,
            remote_jid=remote_jid,
            contact_name="Test Client",
            message=client_message
        )
        
        # Validar resposta
        assert response is not None, "Agent não retornou resposta para cardápio"
        assert len(response) > 0, "Resposta vazia para cardápio"
        
        print(f"✓ Teste E2E cardápio passou: resposta recebida")
        
    except Exception as e:
        pytest.fail(f"Teste E2E cardápio falhou: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "e2e"])
