"""Falha de commit nos serviços de escrita (#94): erro relançado, `rollback` do que ficou pendente e Session utilizável.

O `get_db` fecha a Session por request e mascararia a falta; o Socket.IO e o worker não têm esse fechamento.
"""
import pytest
from sqlalchemy.exc import OperationalError

from app.models import Agent, Instance, PaymentRecord, User
from app.services.company_service import update_agent_settings
from app.services.conversation_service import mark_read
from app.services.instance_service import bind_agent, deactivate, set_agent_enabled, upsert_instance_for_user
from app.services.refund_service import close_refund
from tests.access_helpers import make_company, make_conversation, make_instance, make_user
from tests.order_helpers import make_order


@pytest.fixture
def fail_next_commit(db, monkeypatch):
    """Arma o `commit` para falhar como um banco que cai no meio da escrita. Chamar DEPOIS de preparar os dados."""

    def arm():
        def boom():
            raise OperationalError("COMMIT", {}, Exception("banco fora"))

        monkeypatch.setattr(db, "commit", boom)

    return arm


def _assert_usable(db):
    assert db.query(Instance).count() >= 0  # a Session não ficou presa em transação inválida


def test_set_agent_enabled_discards_the_pending_change(db, fail_next_commit):
    instance = make_instance(db, "inst", None, agent_enabled=False)
    fail_next_commit()

    with pytest.raises(OperationalError):
        set_agent_enabled(db, instance, True)

    assert instance.agent_enabled is False  # relê do banco: a alteração pendente foi descartada
    _assert_usable(db)


def test_bind_agent_discards_the_pending_change(db, fail_next_commit):
    instance = make_instance(db, "inst", None, agent_enabled=True)
    fail_next_commit()

    with pytest.raises(OperationalError):
        bind_agent(db, instance, None)

    assert (instance.agent_id, instance.agent_enabled) == (None, True)
    _assert_usable(db)


def test_deactivate_discards_the_pending_change(db, fail_next_commit):
    instance = make_instance(db, "inst", None)
    fail_next_commit()

    with pytest.raises(OperationalError):
        deactivate(db, instance.id)

    assert (instance.is_active, instance.status) == (True, "disconnected")
    _assert_usable(db)


def test_mark_read_discards_the_pending_change(db, fail_next_commit):
    conversation = make_conversation(db, make_instance(db, "inst", None))
    conversation.unread_count = 3
    db.commit()
    fail_next_commit()

    with pytest.raises(OperationalError):
        mark_read(db, conversation)

    assert conversation.unread_count == 3
    _assert_usable(db)


def test_close_refund_discards_the_pending_change(db, fail_next_commit):
    order = make_order(db, make_instance(db, "inst", None), "R-1", "cancelled", pix="paid")
    record = db.query(PaymentRecord).filter_by(order_id=order.id).one()
    record.refund_status = "pending"
    db.commit()
    fail_next_commit()

    with pytest.raises(OperationalError):
        close_refund(db, record, "refunded")

    assert (record.refund_status, record.refunded_at) == ("pending", None)
    _assert_usable(db)


def test_update_agent_settings_discards_the_pending_change(db, fail_next_commit):
    company = make_company(db, "Pizzaria", with_agent=True)
    agent = db.query(Agent).filter_by(company_id=company.id).one()
    original = agent.name
    fail_next_commit()

    with pytest.raises(OperationalError):
        update_agent_settings(db, agent, {"name": "Novo nome"})

    assert agent.name == original
    _assert_usable(db)


def test_upsert_instance_for_user_discards_the_new_row(client, db, fail_next_commit):
    make_user(client, db, "dono@example.com")
    user = db.query(User).one()
    fail_next_commit()

    with pytest.raises(OperationalError):
        upsert_instance_for_user(db, "inst-nova", user, None)

    assert db.query(Instance).count() == 0
