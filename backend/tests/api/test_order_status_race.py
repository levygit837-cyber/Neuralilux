"""Corrida entre a Company e o Contact sobre o mesmo Order (#34): a transição é condicional, só uma vence."""
import pytest

from app.models import CustomerOrder, Instance, Message, PaymentRecord
from app.packs.catalog_orders.changes import OrderChanged, cancel_order
from app.services.order_status import TransitionError, change_status
from tests.access_helpers import fake_text_sender
from tests.conftest import TestingSessionLocal
from tests.order_helpers import make_order

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sessions(db):
    """Sessões independentes, como dois processos lendo o mesmo Order antes de qualquer escrita."""
    opened = []

    def open_session():
        opened.append(TestingSessionLocal())
        return opened[-1]

    yield open_session
    for session in opened:
        session.close()


@pytest.fixture
def order_id(db):
    instance = Instance(name="inst-race", evolution_instance_id="inst-race", is_active=True)
    db.add(instance)
    db.commit()
    return make_order(db, instance, "R-1", "closed", pix="pending").id


@pytest.fixture
def sender(monkeypatch):
    return fake_text_sender(monkeypatch)


def read_state(db, order_id):
    db.expire_all()
    order = db.get(CustomerOrder, order_id)
    pix = db.query(PaymentRecord).filter_by(order_id=order_id).one()
    return order.status, pix.status, pix.refund_status, db.query(Message).count()


async def test_two_company_moves_from_the_same_read_state_only_one_wins(db, sessions, order_id, sender):
    first, second = sessions(), sessions()
    seen_by_first, seen_by_second = first.get(CustomerOrder, order_id), second.get(CustomerOrder, order_id)
    assert seen_by_first.status == seen_by_second.status == "closed"

    await change_status(first, seen_by_first, "in_production")
    with pytest.raises(TransitionError):
        await change_status(second, seen_by_second, "cancelled")

    assert read_state(db, order_id) == ("in_production", "pending", None, 1)  # Pix intacto, um aviso só
    assert sender.await_count == 1


async def test_company_cancel_loses_nothing_when_the_contact_cancelled_first(db, sessions, order_id, sender):
    contact_side, company_side = sessions(), sessions()
    seen_by_contact, seen_by_company = contact_side.get(CustomerOrder, order_id), company_side.get(CustomerOrder, order_id)

    cancel_order(contact_side, seen_by_contact, "mudei de ideia")
    contact_side.commit()
    with pytest.raises(TransitionError):
        await change_status(company_side, seen_by_company, "in_production")

    assert read_state(db, order_id) == ("cancelled", "cancelled", "verify", 0)  # sem aviso de "em preparo" num pedido cancelado
    assert sender.await_count == 0


async def test_contact_cancel_loses_when_the_company_started_preparing_first(db, sessions, order_id, sender):
    contact_side, company_side = sessions(), sessions()
    seen_by_contact, seen_by_company = contact_side.get(CustomerOrder, order_id), company_side.get(CustomerOrder, order_id)

    await change_status(company_side, seen_by_company, "in_production")
    with pytest.raises(OrderChanged):
        cancel_order(contact_side, seen_by_contact, "mudei de ideia")
    contact_side.commit()

    assert read_state(db, order_id) == ("in_production", "pending", None, 1)  # o Pix continua válido, sem estorno
    order = db.get(CustomerOrder, order_id)
    assert order.cancelled_at is None and order.cancel_reason is None
