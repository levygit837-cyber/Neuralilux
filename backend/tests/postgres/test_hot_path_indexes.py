"""#90: índices do caminho quente, unicidade de Contact/Conversation e a fusão de duplicatas da migração 0015."""
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.agent import memory
from app.models import (
    Contact,
    Conversation,
    ConversationMemorySummary,
    CustomerOrder,
    Instance,
    Message,
    Ticket,
)
from app.whatsapp.message_store import get_or_create_contact, get_or_create_conversation
from tests.postgres.alembic_runner import run_alembic

pytestmark = pytest.mark.postgres

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
JID = "5511999990001@s.whatsapp.net"


# ---------- migração 0015: fusão das duplicatas ----------


def _message(conversation: Conversation, message_id: str, minutes: int) -> Message:
    return Message(
        id=f"msg-{message_id}", instance_id=conversation.instance_id, conversation_id=conversation.id,
        remote_jid=conversation.remote_jid, message_id=message_id, message_type="text", content=f"texto {message_id}",
        direction="incoming", timestamp=T0 + timedelta(minutes=minutes),
    )


def _seed_duplicates(engine) -> dict:
    """Banco na 0014 (sem as unicidades) com Contacts e Conversations duplicados e filhos pendurados nos duplicados."""
    with Session(engine) as db:
        instance = Instance(id="inst-1", name="inst", evolution_instance_id="evo-dup")
        db.add(instance)
        db.flush()

        # Contact duplicado: o mais antigo só tem o número como nome; o mais novo tem nome, pushName e notas.
        old_contact = Contact(
            id="c-old", instance_id=instance.id, phone_number="5511999990001", remote_jid=JID,
            name="5511999990001", created_at=T0, updated_at=T0,
        )
        new_contact = Contact(
            id="c-new", instance_id=instance.id, phone_number="5511999990001", remote_jid=JID,
            name="Ana", push_name="Ana", notes="vip", created_at=T0 + timedelta(hours=1), updated_at=T0 + timedelta(hours=1),
        )
        other_contact = Contact(
            id="c-other", instance_id=instance.id, phone_number="5511999990002",
            remote_jid="5511999990002@s.whatsapp.net", name="Bia", created_at=T0, updated_at=T0,
        )
        db.add_all([old_contact, new_contact, other_contact])
        db.flush()

        # Cada Contact duplicado tem a sua Conversation: depois de fundir os Contacts, viram duas na mesma chave.
        old_conv = Conversation(
            id="k-old", instance_id=instance.id, contact_id=old_contact.id, remote_jid=JID, unread_count=2,
            last_message_at=T0 + timedelta(minutes=5), last_message_preview="antigo", created_at=T0,
            human_in_loop=False, is_active=True,
        )
        new_conv = Conversation(
            id="k-new", instance_id=instance.id, contact_id=new_contact.id, remote_jid=JID, unread_count=3,
            last_message_at=T0 + timedelta(minutes=50), last_message_preview="novo", created_at=T0 + timedelta(hours=1),
            human_in_loop=False, is_active=True,
        )
        other_conv = Conversation(
            id="k-other", instance_id=instance.id, contact_id=other_contact.id, remote_jid=other_contact.remote_jid,
            unread_count=7, created_at=T0, human_in_loop=False, is_active=True,
        )
        db.add_all([old_conv, new_conv, other_conv])
        db.flush()

        ticket = Ticket(
            id="t-1", conversation_id=new_conv.id, instance_id=instance.id, contact_id=new_contact.id,
            agent_type="handoff", reason="cliente pediu humano", content="quero falar com alguém",
        )
        db.add(ticket)
        db.flush()
        new_conv.human_in_loop, new_conv.human_handoff_reason, new_conv.ticket_id = True, "cliente pediu humano", ticket.id

        order = CustomerOrder(
            id="o-1", order_number="P-1", conversation_id=new_conv.id, instance_id=instance.id,
            contact_id=new_contact.id, remote_jid=JID, status="closed", total_amount=Decimal("95.00"),
            delivery_fee=Decimal("5.00"), customer_name="Ana", payment_method="pix", delivery_type="entrega",
            opened_at=T0, closed_at=T0,
        )
        orphan = Message(
            id="msg-orphan", instance_id=instance.id, conversation_id=None, remote_jid=JID, message_id="orphan",
            direction="incoming", timestamp=T0,
        )
        messages = [_message(old_conv, "a1", 1), _message(old_conv, "a2", 2), _message(new_conv, "b1", 10),
                    _message(new_conv, "b2", 11), _message(new_conv, "b3", 12), _message(other_conv, "z1", 3)]
        db.add_all([order, orphan, *messages])
        db.flush()

        # Duas Conversations duplicadas do mesmo Contact, cada uma com Summary (filho de chave única).
        twin_contact = Contact(
            id="c-twin", instance_id=instance.id, phone_number="5511999990003",
            remote_jid="5511999990003@s.whatsapp.net", name="Caio", created_at=T0, updated_at=T0,
        )
        db.add(twin_contact)
        db.flush()
        twins = [
            Conversation(
                id=f"k-twin-{n}", instance_id=instance.id, contact_id=twin_contact.id, remote_jid=twin_contact.remote_jid,
                created_at=T0 + timedelta(minutes=n), human_in_loop=False, is_active=True,
            )
            for n in (1, 2)
        ]
        db.add_all(twins)
        db.flush()
        twin_messages = [_message(twin, f"t{n}", n) for n, twin in enumerate(twins, start=20)]
        db.add_all(twin_messages)
        db.flush()
        db.add_all([
            ConversationMemorySummary(
                conversation_id=twin.id, summary=f"resumo {twin.id}", covered_until_message_id=twin_message.id, message_count=1,
            )
            for twin, twin_message in zip(twins, twin_messages)
        ])
        db.commit()
        return {"messages": db.query(Message).count()}


def test_migration_0015_merges_duplicates_without_losing_messages(make_database):
    url = make_database()
    engine = create_engine(url)
    try:
        run_alembic(url, "upgrade", "0014")
        before = _seed_duplicates(engine)

        result = run_alembic(url, "upgrade", "0015")

        assert "fundiu 2 Contact(s) e 2 Conversation(s)" not in result.stderr  # 1 Contact e 2 Conversations, abaixo
        assert "fundiu 1 Contact(s) e 2 Conversation(s)" in result.stderr
        with Session(engine) as db:
            contacts = {c.id: c for c in db.query(Contact).filter(Contact.remote_jid == JID)}
            assert list(contacts) == ["c-old"]  # fica o mais antigo
            survivor = contacts["c-old"]
            assert (survivor.name, survivor.push_name, survivor.notes) == ("Ana", "Ana", "vip")

            conversations = {c.id: c for c in db.query(Conversation).filter(Conversation.contact_id == "c-old")}
            assert list(conversations) == ["k-old"]
            merged = conversations["k-old"]
            assert merged.unread_count == 5
            assert (merged.last_message_preview, merged.last_message_at) == ("novo", T0 + timedelta(minutes=50))
            assert (merged.human_in_loop, merged.human_handoff_reason, merged.ticket_id) == (
                True, "cliente pediu humano", "t-1",
            )

            # Nenhuma Message se perdeu; as da Conversation duplicada foram para a que ficou.
            assert db.query(Message).count() == before["messages"]
            by_conversation = {m.message_id: m.conversation_id for m in db.query(Message)}
            assert {by_conversation[i] for i in ("a1", "a2", "b1", "b2", "b3")} == {"k-old"}
            assert by_conversation["orphan"] is None and by_conversation["z1"] == "k-other"

            # Filhos que apontavam para os duplicados (descobertos pelas FKs) foram reapontados.
            order = db.get(CustomerOrder, "o-1")
            assert (order.contact_id, order.conversation_id) == ("c-old", "k-old")
            ticket = db.get(Ticket, "t-1")
            assert (ticket.contact_id, ticket.conversation_id) == ("c-old", "k-old")

            # Filho de chave única (Summary): sobra um, o da Conversation mais antiga.
            twin = db.query(Conversation).filter(Conversation.contact_id == "c-twin").one()
            assert twin.id == "k-twin-1"
            summaries = db.query(ConversationMemorySummary).filter(ConversationMemorySummary.conversation_id.like("k-twin-%")).all()
            assert [(s.conversation_id, s.summary) for s in summaries] == [("k-twin-1", "resumo k-twin-1")]

            # O que não era duplicado não mudou.
            assert db.get(Conversation, "k-other").unread_count == 7
            assert db.get(Contact, "c-other").name == "Bia"

        with pytest.raises(Exception, match="uq_contacts_instance_remote_jid"):
            with Session(engine) as db:
                db.add(Contact(instance_id="inst-1", phone_number="1", remote_jid=JID, name="outro"))
                db.commit()

        # O downgrade tira índices e unicidades, não desfaz a fusão.
        run_alembic(url, "downgrade", "0014")
        inspector = inspect(engine)
        assert {c["name"] for c in inspector.get_unique_constraints("contacts")} == set()
        assert "ix_messages_conversation_timestamp" not in {i["name"] for i in inspector.get_indexes("messages")}
        with Session(engine) as db:
            assert db.query(Message).count() == before["messages"]
            assert db.query(Contact).filter(Contact.remote_jid == JID).count() == 1
    finally:
        engine.dispose()


def test_migration_0015_without_duplicates_creates_indexes_and_logs_zero(make_database):
    url = make_database()
    engine = create_engine(url)
    try:
        run_alembic(url, "upgrade", "0014")
        result = run_alembic(url, "upgrade", "0015")

        assert "fundiu 0 Contact(s) e 0 Conversation(s)" in result.stderr
        inspector = inspect(engine)
        assert {i["name"] for i in inspector.get_indexes("messages")} >= {
            "ix_messages_conversation_timestamp", "ix_messages_instance_timestamp",
        }
        assert {i["name"] for i in inspector.get_indexes("conversations")} >= {
            "ix_conversations_instance_last_message_at", "ix_conversations_contact_id",
        }
    finally:
        engine.dispose()


# ---------- EXPLAIN: as queries reais usam índice ----------


@pytest.fixture(scope="module")
def populated_engine(make_database):
    """Banco migrado com volume suficiente para o planner preferir índice: 20 Instances, 30 mil Conversations, 100 mil Messages."""
    url = make_database()
    run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO instances (id, name, evolution_instance_id)
            SELECT 'i' || n, 'inst' || n, 'evo' || n FROM generate_series(0, 19) n
        """))
        conn.execute(text("""
            INSERT INTO contacts (id, instance_id, phone_number, remote_jid)
            SELECT 'c' || n, 'i' || (n % 20), 'p' || n, n || '@s.whatsapp.net' FROM generate_series(1, 30000) n
        """))
        conn.execute(text("""
            INSERT INTO conversations (id, instance_id, contact_id, remote_jid, human_in_loop, is_active, last_message_at)
            SELECT 'k' || n, 'i' || (n % 20), 'c' || n, n || '@s.whatsapp.net', false, true,
                   CASE WHEN n % 10 = 0 THEN NULL ELSE now() - n * interval '1 minute' END
            FROM generate_series(1, 30000) n
        """))
        conn.execute(text("""
            INSERT INTO messages (id, instance_id, conversation_id, remote_jid, message_id, message_type, content, direction, timestamp)
            SELECT 'm' || n, 'i' || (c % 20), 'k' || c, c || '@s.whatsapp.net', 'w' || n, 'text', 'oi', 'incoming',
                   now() - n * interval '5 minutes'
            FROM (SELECT n, 1 + (n * 7919) % 30000 AS c FROM generate_series(1, 100000) n) rows
        """))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ANALYZE"))
    yield engine
    engine.dispose()


def _plan(engine, query) -> str:
    sql = str(query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    with engine.connect() as conn:
        return "\n".join(row[0] for row in conn.execute(text(f"EXPLAIN {sql}")))


@pytest.fixture
def explain_db(populated_engine):
    with Session(populated_engine) as db:
        yield db


def test_recent_window_query_uses_the_conversation_timestamp_index(populated_engine, explain_db):
    conversation = explain_db.get(Conversation, "k77")

    plan = _plan(populated_engine, memory._oldest_first(memory._session_messages(explain_db, conversation)))

    print("\nRecent Window:\n" + plan)
    assert "ix_messages_conversation_timestamp" in plan
    assert "Seq Scan on messages" not in plan


def test_handoff_and_session_lookups_use_the_conversation_timestamp_index(populated_engine, explain_db):
    latest_incoming = (
        explain_db.query(Message)
        .filter(Message.conversation_id == "k77", Message.direction == "incoming", Message.content.isnot(None))
        .order_by(Message.timestamp.desc())
        .limit(1)
    )
    previous = explain_db.query(Message.timestamp).filter(Message.conversation_id == "k77").order_by(
        Message.timestamp.desc(), Message.id.desc()
    ).limit(1)

    handoff_plan, session_plan = _plan(populated_engine, latest_incoming), _plan(populated_engine, previous)

    print("\nHandoff (última Message recebida):\n" + handoff_plan + "\nSession (Message anterior):\n" + session_plan)
    assert "ix_messages_conversation_timestamp" in handoff_plan and "Seq Scan" not in handoff_plan
    assert "ix_messages_conversation_timestamp" in session_plan and "Seq Scan" not in session_plan


def test_conversation_list_query_uses_the_instance_last_message_index(populated_engine, explain_db):
    query = (
        explain_db.query(Conversation)
        .filter(Conversation.instance_id == "i3")
        .order_by(Conversation.last_message_at.desc().nullslast())
        .offset(0)
        .limit(20)
    )

    plan = _plan(populated_engine, query)

    print("\nLista de Conversations:\n" + plan)
    assert "ix_conversations_instance_last_message_at" in plan
    assert "Seq Scan" not in plan and "Sort" not in plan  # a ordem sai do índice, sem ordenar 1500 linhas


def test_dashboard_message_window_uses_the_instance_timestamp_index(populated_engine, explain_db):
    query = explain_db.query(Message.id).filter(
        Message.instance_id.in_(["i3"]), Message.timestamp >= datetime.now(timezone.utc) - timedelta(days=1)
    )

    plan = _plan(populated_engine, query)

    print("\nDashboard (Messages de hoje):\n" + plan)
    assert "ix_messages_instance_timestamp" in plan and "Seq Scan" not in plan


def test_contact_lookup_by_instance_and_jid_uses_the_unique_index(populated_engine, explain_db):
    query = explain_db.query(Contact).filter(Contact.instance_id == "i3", Contact.remote_jid == "23@s.whatsapp.net")

    plan = _plan(populated_engine, query)

    print("\nget_or_create_contact:\n" + plan)
    assert "uq_contacts_instance_remote_jid" in plan and "Seq Scan" not in plan


# ---------- corrida de criação ----------


@pytest.fixture
def race_engine(make_database):
    url = make_database()
    run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    with Session(engine) as db:
        db.add(Instance(id="inst-race", name="race", evolution_instance_id="evo-race"))
        db.commit()
    yield engine
    engine.dispose()


def _wait_until_insert_blocks(engine, table: str, timeout: float = 10.0) -> None:
    """Espera um INSERT na `table` ficar parado esperando o lock de outra transação (a que venceu a corrida)."""
    deadline = time.monotonic() + timeout
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            blocked = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock' AND query ILIKE :pattern"
                ),
                {"pattern": f"INSERT INTO {table}%"},
            ).scalar()
            if blocked:
                return
            conn.rollback()
            time.sleep(0.05)
    raise AssertionError(f"nenhum INSERT em {table} ficou esperando o outro processo")


def _race(engine, table: str, create):
    """Duas sessões criam a mesma linha ao mesmo tempo: a segunda para no INSERT até a primeira confirmar.

    `create(session)` devolve uma tupla de valores simples (ids, flags), lida antes do commit para não
    depender de objetos ligados à sessão. A primeira cria sem confirmar; a segunda começa numa thread (o
    SELECT dela não vê a linha da primeira) e trava no INSERT; só então a primeira confirma.
    """
    winner_db, loser_db = Session(engine), Session(engine)
    outcome: dict = {}
    try:
        winner_result = create(winner_db)

        def loser():
            try:
                outcome["result"] = create(loser_db)
                loser_db.commit()
            except Exception as error:  # noqa: BLE001 - a thread devolve o erro para o teste
                outcome["error"] = error

        thread = threading.Thread(target=loser)
        thread.start()
        _wait_until_insert_blocks(engine, table)
        winner_db.commit()
        thread.join(timeout=10)
        assert not thread.is_alive(), "a segunda criação não terminou depois de a primeira confirmar"
        return winner_result, outcome
    finally:
        winner_db.close()
        loser_db.close()


def test_concurrent_contact_creation_results_in_a_single_row(race_engine):
    def create(db):
        instance = db.get(Instance, "inst-race")
        return (get_or_create_contact(db, instance, JID, push_name="Ana").id,)

    (winner_id,), outcome = _race(race_engine, "contacts", create)

    assert "error" not in outcome, outcome.get("error")
    assert outcome["result"] == (winner_id,)  # quem perdeu a corrida recebeu a linha do vencedor
    with Session(race_engine) as db:
        assert db.query(Contact).filter(Contact.remote_jid == JID).count() == 1


def test_concurrent_conversation_creation_results_in_a_single_row(race_engine):
    with Session(race_engine) as db:
        instance = db.get(Instance, "inst-race")
        contact_id = get_or_create_contact(db, instance, JID).id
        db.commit()

    def create(db):
        instance = db.get(Instance, "inst-race")
        conversation, created = get_or_create_conversation(db, instance, db.get(Contact, contact_id), JID)
        return conversation.id, created

    (winner_id, winner_created), outcome = _race(race_engine, "conversations", create)

    assert "error" not in outcome, outcome.get("error")
    assert winner_created is True
    assert outcome["result"] == (winner_id, False)
    with Session(race_engine) as db:
        assert db.query(Conversation).filter(Conversation.contact_id == contact_id).count() == 1


def test_get_or_create_contact_keeps_working_inside_an_open_transaction(race_engine):
    """O perdedor da corrida não leva `IntegrityError`, então a transação de quem chamou segue utilizável."""
    with Session(race_engine) as db:
        instance = db.get(Instance, "inst-race")
        first = get_or_create_contact(db, instance, JID)
        again = get_or_create_contact(db, instance, JID, push_name="Ana")
        db.flush()
        assert again.id == first.id and again.push_name == "Ana"
        assert db.execute(select(Contact.id).where(Contact.remote_jid == JID)).all() == [(first.id,)]
        db.rollback()


def test_fake_instance_namespace_is_enough_for_get_or_create_keys(race_engine):
    """`get_or_create_*` só usa `instance.id`: o helper não depende de mais nada da Instance."""
    with Session(race_engine) as db:
        contact = get_or_create_contact(db, SimpleNamespace(id="inst-race"), "5511999990009@s.whatsapp.net")
        assert contact.instance_id == "inst-race"
        db.rollback()
