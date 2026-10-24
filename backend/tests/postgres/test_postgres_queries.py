"""Queries que só existem no Postgres: History Search (FTS), índice parcial do Payment Record e `to_char`."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.agent import memory
from app.api.routes.dashboard import get_satisfaction_metrics
from app.models import Company, Contact, Conversation, CustomerOrder, Instance, Message, PaymentRecord, User
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.pix import ensure_payment_record

pytestmark = pytest.mark.postgres

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _conversation(pg, tag: str, remote_jid: str = "5511999999999@s.whatsapp.net") -> Conversation:
    instance = Instance(name=f"inst-{tag}", evolution_instance_id=f"evo-{tag}")
    pg.add(instance)
    pg.flush()
    contact = Contact(instance_id=instance.id, phone_number=remote_jid.split("@")[0], remote_jid=remote_jid, name="Cliente")
    pg.add(contact)
    pg.flush()
    conversation = Conversation(instance_id=instance.id, contact_id=contact.id, remote_jid=remote_jid)
    pg.add(conversation)
    pg.flush()
    return conversation


def _say(pg, conversation: Conversation, n: int, content: str, role: str = "user") -> None:
    pg.add(Message(
        instance_id=conversation.instance_id, conversation_id=conversation.id, remote_jid=conversation.remote_jid,
        message_type="text", content=content, direction="incoming" if role == "user" else "outgoing",
        is_from_me=role == "assistant", timestamp=T0 + timedelta(minutes=n),
    ))
    pg.flush()


def _order(pg, conversation: Conversation, number: str) -> CustomerOrder:
    order = CustomerOrder(
        order_number=number, conversation_id=conversation.id, instance_id=conversation.instance_id,
        contact_id=conversation.contact_id, remote_jid=conversation.remote_jid, status="closed",
        total_amount=Decimal("95.00"), delivery_fee=Decimal("5.00"), customer_name="Maria",
        payment_method="pix", delivery_type="entrega", opened_at=T0, closed_at=T0,
    )
    pg.add(order)
    pg.flush()
    return order


def _pix(order: CustomerOrder, status: str, method: str = "pix") -> PaymentRecord:
    return PaymentRecord(
        order_id=order.id, conversation_id=order.conversation_id, amount=Decimal("95.00"),
        pix_key="k@pix", payment_method=method, status=status,
    )


def test_history_search_stems_portuguese_and_ranks_by_relevance(pg):
    conversation = _conversation(pg, "fts-rank")
    _say(pg, conversation, 1, "queria uma pizza")
    _say(pg, conversation, 2, "pizza pizza pizza de calabresa, pizza grande")
    _say(pg, conversation, 3, "vocês abrem domingo?")

    hits = memory.search_history(pg, conversation.contact_id, conversation.instance_id, "pizzas")

    # O stemmer `portuguese` casa "pizzas" com "pizza"; o SQLite (ILIKE) não faria isso.
    assert [h["snippet"] for h in hits] == [
        "pizza pizza pizza de calabresa, pizza grande",
        "queria uma pizza",
    ]


def test_history_search_websearch_syntax_and_scope(pg):
    mine = _conversation(pg, "fts-mine", "5511111111111@s.whatsapp.net")
    other = _conversation(pg, "fts-other", "5522222222222@s.whatsapp.net")
    _say(pg, mine, 1, "pizza de calabresa")
    _say(pg, mine, 2, "pizza de queijo")
    _say(pg, other, 3, "pizza de calabresa do outro cliente")

    include = memory.search_history(pg, mine.contact_id, mine.instance_id, "pizza")
    exclude = memory.search_history(pg, mine.contact_id, mine.instance_id, "pizza -queijo")

    assert {h["snippet"] for h in include} == {"pizza de calabresa", "pizza de queijo"}
    assert [h["snippet"] for h in exclude] == ["pizza de calabresa"]


def test_history_search_uses_the_gin_index(pg):
    pg.execute(text("SET LOCAL enable_seqscan = off"))  # tabela vazia: sem isto o planner prefere o seq scan
    plan = "\n".join(
        row[0]
        for row in pg.execute(text(
            "EXPLAIN SELECT id FROM messages "
            "WHERE to_tsvector('portuguese', coalesce(content,'')) @@ websearch_to_tsquery('portuguese', 'pizza')"
        ))
    )

    assert "ix_messages_content_fts" in plan


def test_payment_record_allows_a_single_valid_pix_per_order(pg):
    order = _order(pg, _conversation(pg, "pix-unique"), "PED-0001")
    pg.add(_pix(order, "pending"))
    pg.flush()

    pg.add(_pix(order, "paid"))
    with pytest.raises(IntegrityError, match="uq_payment_records_order_pix"):
        pg.flush()


def test_payment_record_index_ignores_invalid_and_non_pix_rows(pg):
    order = _order(pg, _conversation(pg, "pix-partial"), "PED-0002")
    for status in ("cancelled", "superseded", "expired"):
        pg.add(_pix(order, status))
    pg.add(_pix(order, "pending", method="dinheiro"))
    pg.add(_pix(order, "pending"))  # o único Pix válido: os demais não contam para o índice
    pg.flush()

    assert pg.query(PaymentRecord).filter_by(order_id=order.id).count() == 5


def test_ensure_payment_record_returns_the_winner_when_the_index_rejects_the_insert(pg, monkeypatch):
    conversation = _conversation(pg, "pix-ensure")
    order = _order(pg, conversation, "PED-0003")
    company = Company(name="Macedos", pix_key="pix@macedos.example", address_city="Fortaleza")
    pg.add(company)
    winner = _pix(order, "pending")
    pg.add(winner)
    pg.commit()  # o vencedor já está gravado: o rollback do perdedor não pode levá-lo junto
    winner_id = winner.id

    # Simula a corrida: a leitura prévia não enxerga o vencedor, só o índice o barra.
    original = pix._existing_record
    calls = []

    def blind_first_read(db, order_id):
        calls.append(order_id)
        return None if len(calls) == 1 else original(db, order_id)

    monkeypatch.setattr(pix, "_existing_record", blind_first_read)
    record = ensure_payment_record(pg, order, company)

    assert record.id == winner_id
    assert len(calls) == 2


def test_satisfaction_metrics_groups_ratings_by_month_with_to_char(pg):
    conversation = _conversation(pg, "csat")
    now = datetime.now(timezone.utc)
    conversation.rating = 4
    conversation.updated_at = now
    other = _conversation(pg, "csat-other", remote_jid="5511888888888@s.whatsapp.net")  # um Contact por Conversation
    other.rating = 5
    other.updated_at = now
    pg.flush()
    admin = User(email="csat@example.com", hashed_password="x", is_superuser=True)

    result = asyncio.run(get_satisfaction_metrics(db=pg, current_user=admin))

    assert result["history"] == [{"month": now.strftime("%Y-%m"), "score": 4.5}]
    assert result["current_score"] == 4.5
