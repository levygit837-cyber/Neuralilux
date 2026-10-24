"""#91: dois workers que tomam a mesma Message pendente ao mesmo tempo respondem uma vez só (Postgres de verdade)."""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text, update
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.whatsapp import turn_state
from app.whatsapp.recovery import Recovery
from app.whatsapp.turn_runner import TurnRunner, Work
from tests.postgres.alembic_runner import run_alembic

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
JID = "5511999990001@s.whatsapp.net"


@pytest.fixture
def engine(make_database):
    url = make_database()
    run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    with Session(engine) as db:
        instance = Instance(id="inst-1", name="t", evolution_instance_id="evo-t")
        contact = Contact(id="c-1", instance_id="inst-1", phone_number="5511999990001", remote_jid=JID)
        conversation = Conversation(id="conv-1", instance_id="inst-1", contact_id="c-1", remote_jid=JID)
        db.add_all([instance, contact, conversation])
        db.flush()
        db.add(
            Message(
                id="msg-1", instance_id="inst-1", conversation_id="conv-1", remote_jid=JID, message_id="in-1",
                message_type="text", content="Oi", direction="incoming", timestamp=NOW,
                turn_state=turn_state.PENDING, turn_reason=turn_state.QUEUED, turn_claimed_at=None,
            )
        )
        db.commit()
    yield engine
    engine.dispose()


def _wait_until_update_blocks(engine, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            blocked = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock' AND query ILIKE 'UPDATE messages%'"
                )
            ).scalar()
            if blocked:
                return
            conn.rollback()
            time.sleep(0.05)
    raise AssertionError("nenhum UPDATE ficou esperando o lock da outra transação")


def test_second_claim_waits_for_the_first_and_wins_nothing(engine):
    """A segunda tomada começa enquanto a primeira ainda não confirmou: ao destravar, reavalia o WHERE e não casa."""
    first_at, second_at = NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)
    first_db, second_db = Session(engine), Session(engine)
    outcome: dict = {}
    try:
        first_db.execute(
            update(Message).where(Message.id == "msg-1", Message.turn_claimed_at.is_(None)).values(
                turn_claimed_at=first_at, turn_reason=turn_state.QUEUED
            )
        )  # aberto: segura o lock da linha

        def second():
            outcome["won"] = turn_state.claim(second_db, [("msg-1", None)], second_at, turn_state.QUEUED)

        thread = threading.Thread(target=second)
        thread.start()
        _wait_until_update_blocks(engine)
        first_db.commit()
        thread.join(timeout=10)
        assert not thread.is_alive()
    finally:
        first_db.close()
        second_db.close()

    assert outcome["won"] == {}
    with Session(engine) as db:
        row = db.get(Message, "msg-1")
        assert turn_state.aware(row.turn_claimed_at) == first_at


@pytest.mark.parametrize("round_", range(5))
def test_simultaneous_claims_have_exactly_one_winner(engine, round_):
    barrier = threading.Barrier(4)
    results: list[dict] = []

    def worker(n: int):
        with Session(engine) as db:
            barrier.wait()
            results.append(turn_state.claim(db, [("msg-1", None)], NOW + timedelta(seconds=n), turn_state.QUEUED))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    [t.start() for t in threads]
    [t.join(timeout=10) for t in threads]

    assert sorted(len(won) for won in results) == [0, 0, 0, 1]


def test_two_recovery_sweeps_hand_the_message_to_a_single_turn(engine):
    spawned: list[list[Work]] = []
    barrier = threading.Barrier(2)

    class Runner(TurnRunner):
        def spawn(self, works, hold=None, *, recovered=False):
            spawned.append(works)

        def is_active(self, message_id):
            return False

    def sweep():
        recovery = Recovery(Runner(lambda: Session(engine), lambda _id: None), lambda: Session(engine), lambda: NOW)
        barrier.wait()
        import asyncio

        asyncio.run(recovery.sweep())

    threads = [threading.Thread(target=sweep) for _ in range(2)]
    [t.start() for t in threads]
    [t.join(timeout=15) for t in threads]

    assert [[w.entry.message_id for w in works] for works in spawned] == [["msg-1"]]


def test_pending_rows_have_a_partial_index(engine):
    indexes = {i["name"]: i for i in inspect(engine).get_indexes("messages")}
    assert "ix_messages_turn_pending" in indexes
    with engine.connect() as conn:
        definition = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_messages_turn_pending'")
        ).scalar()
    assert "WHERE" in definition and "pending" in definition
