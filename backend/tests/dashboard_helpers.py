"""Fixture conhecida do dashboard: dois donos, números conferíveis à mão.

Tudo é relativo a `now`. Período de 7 dias (tabela dos números esperados em `ALICE_7D`):

| Conversation | Instance     | criada em | Messages (entrada/saída)                                          |
|--------------|--------------|-----------|-------------------------------------------------------------------|
| c1           | Loja Centro  | now-1d    | in, out do Agent, in, aviso do sistema, in (3 entradas, 1 respondida) |
| c2           | Loja Centro  | now-2d    | in, out de um Attendant (1 entrada, 1 respondida)                 |
| grupo        | Loja Centro  | now-1d    | in (grupo: fora de todos os números)                              |
| c3           | Loja Norte   | now-10d   | in, out, in (período anterior: 2 entradas, 1 respondida)          |

Tickets de Alice: `open` em c1 (now-1d), `closed` em c2 (now-2d) e `expired` em c3 (now-10d).
Bob tem uma Conversation, uma Message de entrada e um Ticket `open`, todos em now-1d.
"""
from datetime import datetime, timedelta

from app.models import Contact, Conversation, Instance, Message, Ticket

ALICE_7D = {
    "conversations": (2, 1),
    "messages": (7, 3),
    "handoffs": (2, 1),
    "received": 4,
    "answered": 2,
    "response_rate": 50.0,
    "previous_response_rate": 50.0,
}


def _instance(db, name: str, owner_id: str) -> Instance:
    instance = Instance(name=name, evolution_instance_id=f"evo-{name}", owner_id=owner_id, is_active=True)
    db.add(instance)
    db.flush()
    return instance


def _conversation(db, instance: Instance, tag: str, created_at: datetime, is_group: bool = False) -> Conversation:
    jid = f"{tag}@g.us" if is_group else f"{tag}@s.whatsapp.net"
    contact = Contact(instance_id=instance.id, phone_number=tag, remote_jid=jid, name=tag)
    db.add(contact)
    db.flush()
    conversation = Conversation(
        instance_id=instance.id, contact_id=contact.id, remote_jid=jid, is_group=is_group, created_at=created_at
    )
    db.add(conversation)
    db.flush()
    return conversation


def _message(db, conversation: Conversation, at: datetime, direction: str, sent_by: str | None = None) -> None:
    db.add(Message(
        instance_id=conversation.instance_id, conversation_id=conversation.id, remote_jid=conversation.remote_jid,
        message_type="text", content="texto", direction=direction, is_from_me=direction == "outgoing",
        sent_by=sent_by, timestamp=at,
    ))
    db.flush()


def _ticket(db, conversation: Conversation, created_at: datetime, status: str) -> None:
    db.add(Ticket(
        conversation_id=conversation.id, instance_id=conversation.instance_id, contact_id=conversation.contact_id,
        agent_type="whatsapp_agent", reason="motivo", content="conteúdo", status=status, created_at=created_at,
    ))
    db.flush()


def seed_dashboard(db, now: datetime, *, alice_id: str, bob_id: str) -> dict:
    minute = timedelta(minutes=1)
    centro = _instance(db, "Loja Centro", alice_id)
    norte = _instance(db, "Loja Norte", alice_id)
    bob_instance = _instance(db, "Loja do Bob", bob_id)

    t1 = now - timedelta(days=1)
    c1 = _conversation(db, centro, "c1", t1)
    _message(db, c1, t1, "incoming")
    _message(db, c1, t1 + minute, "outgoing")
    _message(db, c1, t1 + 2 * minute, "incoming")
    _message(db, c1, t1 + 3 * minute, "outgoing", sent_by="system")
    _message(db, c1, t1 + 4 * minute, "incoming")
    _ticket(db, c1, t1, "open")

    t2 = now - timedelta(days=2)
    c2 = _conversation(db, centro, "c2", t2)
    _message(db, c2, t2, "incoming")
    _message(db, c2, t2 + minute, "outgoing")
    _ticket(db, c2, t2, "closed")

    group = _conversation(db, centro, "grupo", t1, is_group=True)
    _message(db, group, t1, "incoming")

    t3 = now - timedelta(days=10)
    c3 = _conversation(db, norte, "c3", t3)
    _message(db, c3, t3, "incoming")
    _message(db, c3, t3 + minute, "outgoing")
    _message(db, c3, t3 + 2 * minute, "incoming")
    _ticket(db, c3, t3, "expired")

    bob_conversation = _conversation(db, bob_instance, "bob", t1)
    _message(db, bob_conversation, t1, "incoming")
    _ticket(db, bob_conversation, t1, "open")

    return {"alice_instances": [centro.id, norte.id], "bob_instances": [bob_instance.id], "c1_created": t1, "c2_created": t2}
