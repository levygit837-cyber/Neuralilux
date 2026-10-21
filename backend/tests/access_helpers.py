"""Helpers dos testes de acesso por dono: usuários, Companies, Instances e Tickets."""
from unittest.mock import AsyncMock

from app.models import Agent, Company, Contact, Conversation, Instance, Ticket, User
from app.whatsapp.evolution_client import evolution_api


def make_company(db, name: str, with_agent: bool = False) -> Company:
    company = Company(name=name, is_active=True)
    db.add(company)
    db.commit()
    if with_agent:
        db.add(Agent(name=f"Agent {name}", system_prompt="prompt", company_id=company.id, is_active=True))
        db.commit()
    return company


def make_user(client, db, email: str, company=None, superuser: bool = False) -> dict:
    """Cria o usuário pelo registro público, ajusta Company/superusuário no banco e devolve os headers."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123", "full_name": email},
    )
    fields = {"is_superuser": superuser}
    if company is not None:
        fields["company_id"] = company.id
    db.query(User).filter(User.email == email).update(fields)
    db.commit()
    token = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "testpass123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def user_id(db, email: str) -> str:
    return db.query(User).filter(User.email == email).one().id


def make_instance(db, name: str, owner_email: str | None, company=None, **extra) -> Instance:
    instance = Instance(
        name=name,
        evolution_instance_id=name,
        status="disconnected",
        is_active=True,
        owner_id=user_id(db, owner_email) if owner_email else None,
        company_id=company.id if company else None,
        **extra,
    )
    db.add(instance)
    db.commit()
    return instance


def make_ticket(db, instance: Instance, reason: str = "Reclamação") -> Ticket:
    contact = Contact(
        instance_id=instance.id,
        phone_number=f"55{instance.id[:8]}",
        remote_jid=f"{instance.id}@s.whatsapp.net",
        name="Cliente",
    )
    db.add(contact)
    db.commit()
    conversation = Conversation(
        instance_id=instance.id, contact_id=contact.id, remote_jid=contact.remote_jid, is_active=True
    )
    db.add(conversation)
    db.commit()
    ticket = Ticket(
        conversation_id=conversation.id,
        instance_id=instance.id,
        contact_id=contact.id,
        agent_type="sac",
        reason=reason,
        content="Conteúdo",
    )
    db.add(ticket)
    db.commit()
    return ticket


def fake_evolution(monkeypatch, instances: list | None = None) -> dict[str, AsyncMock]:
    """Troca o `evolution_api` por mocks: nenhum teste fala com a Evolution real."""
    mocks = {
        "fetch_instances": AsyncMock(return_value=instances or []),
        "get_instance_status": AsyncMock(return_value={"instance": {"state": "open"}}),
        "get_instance_qrcode": AsyncMock(return_value={"base64": "qr-data"}),
        "disconnect_instance": AsyncMock(return_value={"status": "SUCCESS"}),
        "delete_instance": AsyncMock(return_value={"status": "SUCCESS"}),
        "create_instance": AsyncMock(return_value={"instance": {"instanceName": "x"}}),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(evolution_api, name, mock)
    return mocks
