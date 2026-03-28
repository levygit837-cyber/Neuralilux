import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.core.database import Base, SessionLocal, engine
from app.models.models import Agent, Contact, Conversation, Instance, Message, User
from app.workers.whatsapp_consumer import WhatsAppMessageConsumer


@pytest.fixture
def owned_instance(db):
    Base.metadata.create_all(bind=engine)
    user = User(
        id="user-realtime-1",
        email="realtime@example.com",
        hashed_password="hashed",
        full_name="Realtime User",
        is_active=True,
    )
    db.add(user)
    db.flush()

    instance = Instance(
        id="instance-realtime-1",
        name="Realtime Instance",
        evolution_instance_id="evo-realtime-1",
        status="connected",
        is_active=True,
        owner_id=user.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


@pytest.mark.asyncio
async def test_save_message_to_database_handles_evolution_event_shape_and_publishes_realtime(
    db, owned_instance, monkeypatch
):
    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-realtime-1",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-rt-1",
            },
            "message": {"conversation": "Mensagem em tempo real"},
            "pushName": "Contato Teste",
            "messageTimestamp": 1710000000,
        },
    }

    await consumer._save_message_to_database(db, payload)

    contact = db.query(Contact).one()
    conversation = db.query(Conversation).one()
    message = db.query(Message).one()
    expected_timestamp = "2024-03-09T16:00:00+00:00"

    assert contact.remote_jid == "5511999999999@s.whatsapp.net"
    assert contact.name == "Contato Teste"
    assert conversation.remote_jid == "5511999999999@s.whatsapp.net"
    assert conversation.unread_count == 1
    assert message.message_id == "msg-rt-1"
    assert message.content == "Mensagem em tempo real"
    assert published_events == [
        {
            "type": "incoming_message",
            "instance_name": "evo-realtime-1",
            "conversation_id": "5511999999999@s.whatsapp.net",
            "payload": {
                "conversation": {
                        "id": "5511999999999@s.whatsapp.net",
                        "name": "Contato Teste",
                        "lastMessage": "Mensagem em tempo real",
                        "timestamp": expected_timestamp,
                        "unreadCount": 1,
                        "isOnline": False,
                        "avatar": None,
                    },
                    "message": {
                        "id": "msg-rt-1",
                        "conversationId": "5511999999999@s.whatsapp.net",
                        "content": "Mensagem em tempo real",
                        "timestamp": expected_timestamp,
                        "isOutgoing": False,
                        "status": "sent",
                    "sender": {
                        "name": "Contato Teste",
                    },
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_save_message_to_database_creates_placeholder_instance_when_missing(
    db, monkeypatch
):
    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-placeholder-1",
        "data": {
            "key": {
                "remoteJid": "5511888888888@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-placeholder-1",
            },
            "message": {"conversation": "Mensagem sem mapeamento prévio"},
            "pushName": "Contato Novo",
            "messageTimestamp": 1710001234,
        },
    }

    await consumer._save_message_to_database(db, payload)

    instance = db.query(Instance).filter(Instance.evolution_instance_id == "evo-placeholder-1").one()
    message = db.query(Message).filter(Message.message_id == "msg-placeholder-1").one()

    assert instance.name == "evo-placeholder-1"
    assert instance.owner_id is None
    assert message.instance_id == instance.id
    assert published_events[0]["instance_name"] == "evo-placeholder-1"


@pytest.mark.asyncio
async def test_update_message_status_normalizes_and_publishes_realtime_event(
    db, owned_instance, monkeypatch
):
    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    contact = Contact(
        id="contact-realtime-1",
        instance_id=owned_instance.id,
        phone_number="5511999999999",
        remote_jid="5511999999999@s.whatsapp.net",
        name="Contato Teste",
    )
    db.add(contact)
    db.flush()

    conversation = Conversation(
        id="conversation-realtime-1",
        instance_id=owned_instance.id,
        contact_id=contact.id,
        remote_jid=contact.remote_jid,
        is_active=True,
    )
    db.add(conversation)
    db.flush()

    message = Message(
        id="db-message-realtime-1",
        instance_id=owned_instance.id,
        conversation_id=conversation.id,
        remote_jid=contact.remote_jid,
        message_id="msg-status-1",
        message_type="text",
        content="Status test",
        direction="outgoing",
        status="sent",
        is_from_me=True,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(message)
    db.commit()

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-realtime-1",
        "data": {
            "key": {
                "id": "msg-status-1",
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "status": "READ",
        },
    }

    await consumer._update_message_status(db, payload)
    db.refresh(message)

    assert message.status == "read"
    assert published_events == [
        {
            "type": "message_status",
            "instance_name": "evo-realtime-1",
            "conversation_id": "5511999999999@s.whatsapp.net",
            "payload": {
                "messageId": "msg-status-1",
                "status": "read",
            },
        }
    ]


@pytest.mark.asyncio
async def test_connection_update_normalizes_state_and_publishes_realtime_event(
    db, owned_instance, monkeypatch
):
    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-realtime-1",
        "data": {
            "state": "open",
        },
    }

    await consumer._update_connection_status(db, payload)
    db.refresh(owned_instance)

    assert owned_instance.status == "connected"
    assert published_events == [
        {
            "type": "connection_status",
            "instance_name": "evo-realtime-1",
            "payload": {
                "status": "connected",
                "evolutionState": "open",
            },
        }
    ]


@pytest.mark.asyncio
async def test_process_webhook_event_handles_messages_upsert_end_to_end(db, monkeypatch):
    published_events = []
    suffix = uuid4().hex
    instance_name = f"evo-process-{suffix}"
    message_id = f"msg-process-{suffix}"

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    consumer = WhatsAppMessageConsumer()
    payload = {
        "event": "messages.upsert",
        "data": {
            "instance": instance_name,
            "data": {
                "key": {
                    "remoteJid": "5511777777777@s.whatsapp.net",
                    "fromMe": False,
                    "id": message_id,
                },
                "message": {"conversation": "Mensagem processada pelo worker"},
                "pushName": "Contato Worker",
                "messageTimestamp": 1710002222,
            },
        },
    }

    result = await consumer.process_webhook_event(payload)

    verification_db = SessionLocal()
    try:
        instance = verification_db.query(Instance).filter(Instance.evolution_instance_id == instance_name).one()
        message = verification_db.query(Message).filter(Message.message_id == message_id).one()
    finally:
        verification_db.close()

    assert result["status"] == "processed"
    assert instance.name == instance_name
    assert message.instance_id == instance.id
    assert published_events[0]["type"] == "incoming_message"


@pytest.mark.asyncio
async def test_save_message_to_database_handles_group_jid_without_overflow(
    db, monkeypatch
):
    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-group-1",
        "data": {
            "key": {
                "remoteJid": "553388773141-1562969789@g.us",
                "fromMe": False,
                "id": "msg-group-1",
            },
            "message": {"conversation": "Mensagem de grupo"},
            "pushName": "Grupo Teste",
            "messageTimestamp": 1710003333,
        },
    }

    await consumer._save_message_to_database(db, payload)

    contact = db.query(Contact).filter(Contact.remote_jid == "553388773141-1562969789@g.us").one()
    assert contact.phone_number == "553388773141"
    assert published_events[0]["instance_name"] == "evo-group-1"


@pytest.mark.asyncio
async def test_save_message_to_database_does_not_trigger_agent_when_instance_is_disabled(
    db, monkeypatch
):
    async def fake_publish(_event):
        return None

    process_calls = []

    async def fake_process_message(**kwargs):
        process_calls.append(kwargs)
        return "Resposta"

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )
    monkeypatch.setattr(
        "app.agents.agent_executor.whatsapp_agent.process_message",
        fake_process_message,
    )

    user = User(
        id="user-agent-off-1",
        email="agent-off@example.com",
        hashed_password="hashed",
        full_name="Agent Off User",
        is_active=True,
    )
    agent = Agent(
        id="agent-off-1",
        name="Agente Teste",
        system_prompt="Teste",
        is_active=True,
        owner_id=user.id,
    )
    instance = Instance(
        id="instance-agent-off-1",
        name="Agent Off Instance",
        evolution_instance_id="evo-agent-off-1",
        status="connected",
        is_active=True,
        owner_id=user.id,
        agent_id=agent.id,
        agent_enabled=False,
    )
    db.add_all([user, agent, instance])
    db.commit()

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-agent-off-1",
        "data": {
            "key": {
                "remoteJid": "5511666666666@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-agent-off-1",
            },
            "message": {"conversation": "Mensagem para nao responder"},
            "pushName": "Contato OFF",
            "messageTimestamp": 1710004444,
        },
    }

    await consumer._save_message_to_database(db, payload)

    assert process_calls == []


@pytest.mark.asyncio
async def test_save_message_to_database_triggers_agent_when_instance_is_enabled(
    db, monkeypatch
):
    async def fake_publish(_event):
        return None

    process_calls = []

    async def fake_process_message(**kwargs):
        process_calls.append(kwargs)
        return "Resposta"

    monkeypatch.setattr(
        "app.workers.whatsapp_consumer.realtime_event_bus.publish",
        fake_publish,
    )
    monkeypatch.setattr(
        "app.agents.agent_executor.whatsapp_agent.process_message",
        fake_process_message,
    )

    user = User(
        id="user-agent-on-1",
        email="agent-on@example.com",
        hashed_password="hashed",
        full_name="Agent On User",
        is_active=True,
    )
    agent = Agent(
        id="agent-on-1",
        name="Agente Teste ON",
        system_prompt="Teste",
        is_active=True,
        owner_id=user.id,
    )
    instance = Instance(
        id="instance-agent-on-1",
        name="Agent On Instance",
        evolution_instance_id="evo-agent-on-1",
        status="connected",
        is_active=True,
        owner_id=user.id,
        agent_id=agent.id,
        agent_enabled=True,
    )
    db.add_all([user, agent, instance])
    db.commit()

    consumer = WhatsAppMessageConsumer()
    payload = {
        "instance": "evo-agent-on-1",
        "data": {
            "key": {
                "remoteJid": "5511555555555@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-agent-on-1",
            },
            "message": {"conversation": "Mensagem para responder"},
            "pushName": "Contato ON",
            "messageTimestamp": 1710005555,
        },
    }

    await consumer._save_message_to_database(db, payload)

    assert len(process_calls) == 1
    assert process_calls[0]["instance_name"] == "Agent On Instance"
    assert process_calls[0]["message"] == "Mensagem para responder"

