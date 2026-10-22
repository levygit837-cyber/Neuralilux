import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.models import Agent, BusinessType, Company, Instance
from app.whatsapp import consumer as consumer_module
from app.whatsapp.evolution_client import evolution_api
from tests.conftest import TestingSessionLocal


@pytest.fixture
def world(db, monkeypatch):
    """Company com Agent e Instance ligada; Turn, envio e Summary são falsos e registrados."""
    business_type = BusinessType(name="Restaurante", slug="restaurant")
    db.add(business_type)
    db.flush()
    company = Company(name="Pizzaria", business_type_id=business_type.id)
    db.add(company)
    db.flush()
    agent = Agent(name="Atendente", system_prompt="", company_id=company.id, is_active=True)
    db.add(agent)
    db.flush()
    instance = Instance(
        name="evo-t7", evolution_instance_id="evo-t7", company_id=company.id, agent_id=agent.id, agent_enabled=True
    )
    db.add(instance)
    db.commit()

    calls = {"turns": [], "sent": [], "summaries": []}
    sent_ids = iter(f"out-{n}" for n in range(1, 100))

    async def fake_handle_incoming(db, conversation, contact, instance, text, received_at=None):
        calls["turns"].append(text)
        return TurnResult(reply_text="Resposta")

    async def fake_send(*, instance_name, remote_jid, text):
        calls["sent"].append({"instance_name": instance_name, "remote_jid": remote_jid, "text": text})
        return {"key": {"id": next(sent_ids)}}

    async def fake_refresh(conversation_id):
        calls["summaries"].append(conversation_id)

    monkeypatch.setattr(executor, "handle_incoming", fake_handle_incoming)
    monkeypatch.setattr(executor, "refresh_summary", fake_refresh)
    monkeypatch.setattr(evolution_api, "send_text_message", fake_send)
    monkeypatch.setattr(consumer_module, "SessionLocal", TestingSessionLocal)
    calls.update(company=company, agent=agent, instance=instance)
    return calls
