"""Estornos Pix visíveis para a Company, restritos às Instances do usuário, com baixa idempotente (#33)."""
from decimal import Decimal

import pytest

from app.models import Contact, Conversation, CustomerOrder, PaymentRecord
from tests.access_helpers import make_company, make_instance, make_user


def _pix_order(db, instance, number, *, status="cancelled", refund="pending"):
    contact = Contact(instance_id=instance.id, phone_number=f"55{number}", remote_jid=f"{number}@s.whatsapp.net", name="Maria")
    db.add(contact)
    db.flush()
    conversation = Conversation(instance_id=instance.id, contact_id=contact.id, remote_jid=contact.remote_jid)
    db.add(conversation)
    db.flush()
    order = CustomerOrder(
        order_number=number, conversation_id=conversation.id, instance_id=instance.id, contact_id=contact.id,
        remote_jid=contact.remote_jid, status="cancelled", total_amount=Decimal("95.00"), customer_name="Maria",
    )
    db.add(order)
    db.flush()
    record = PaymentRecord(
        order_id=order.id, conversation_id=conversation.id, amount=Decimal("95.00"), pix_key="k@pix",
        payment_method="pix", status=status, refund_status=refund,
    )
    db.add(record)
    db.commit()
    return record


@pytest.fixture
def world(client, db):
    company_a, company_b = make_company(db, "Empresa A"), make_company(db, "Empresa B")
    alice = make_user(client, db, "alice@example.com", company=company_a)
    bob = make_user(client, db, "bob@example.com", company=company_b)
    inst_a = make_instance(db, "inst-a", "alice@example.com", company_a)
    inst_b = make_instance(db, "inst-b", "bob@example.com", company_b)
    return {
        "alice": alice, "bob": bob, "db": db,
        "a": _pix_order(db, inst_a, "A-1"),
        "a_done": _pix_order(db, inst_a, "A-2", refund="refunded"),
        "a_clean": _pix_order(db, inst_a, "A-3", status="pending", refund=None),
        "a_verify": _pix_order(db, inst_a, "A-4", status="superseded", refund="verify"),
        "b": _pix_order(db, inst_b, "B-1"),
    }


def test_company_sees_only_its_own_open_refunds(client, world):
    body = client.get("/api/v1/orders/refunds", headers=world["alice"]).json()
    assert {r["id"]: r["refund_status"] for r in body["refunds"]} == {world["a"].id: "pending", world["a_verify"].id: "verify"}
    row = next(r for r in body["refunds"] if r["id"] == world["a"].id)
    assert row["order_number"] == "A-1" and row["amount"] == 95.0 and row["customer_name"] == "Maria"


def test_marking_a_refund_as_done_removes_it_from_the_pending_list(client, world):
    response = client.post(f"/api/v1/orders/refunds/{world['a'].id}/refunded", headers=world["alice"])
    assert response.status_code == 200 and response.json()["refund_status"] == "refunded"
    open_ids = [r["id"] for r in client.get("/api/v1/orders/refunds", headers=world["alice"]).json()["refunds"]]
    assert open_ids == [world["a_verify"].id]
    world["db"].expire_all()
    assert world["db"].get(PaymentRecord, world["a"].id).refunded_at is not None


def test_marking_the_same_refund_twice_is_idempotent(client, world):
    url = f"/api/v1/orders/refunds/{world['a'].id}/refunded"
    first = client.post(url, headers=world["alice"])
    world["db"].expire_all()
    stamp = world["db"].get(PaymentRecord, world["a"].id).refunded_at
    second = client.post(url, headers=world["alice"])

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    world["db"].expire_all()
    assert world["db"].get(PaymentRecord, world["a"].id).refunded_at == stamp  # a segunda chamada não regrava


def test_unpaid_pix_can_be_dismissed_after_checking_the_bank(client, world):
    url = f"/api/v1/orders/refunds/{world['a_verify'].id}/dismissed"
    assert client.post(url, headers=world["alice"]).json()["refund_status"] == "dismissed"
    assert client.post(url, headers=world["alice"]).status_code == 200
    ids = [r["id"] for r in client.get("/api/v1/orders/refunds", headers=world["alice"]).json()["refunds"]]
    assert ids == [world["a"].id]


def test_contradicting_a_closed_refund_is_409_and_keeps_the_state(client, world):
    response = client.post(f"/api/v1/orders/refunds/{world['a_done'].id}/dismissed", headers=world["alice"])
    assert response.status_code == 409
    world["db"].expire_all()
    assert world["db"].get(PaymentRecord, world["a_done"].id).refund_status == "refunded"


def test_refunds_require_a_token(client, world):
    assert client.get("/api/v1/orders/refunds").status_code == 401
    assert client.post(f"/api/v1/orders/refunds/{world['a'].id}/refunded").status_code == 401
    assert client.post(f"/api/v1/orders/refunds/{world['a'].id}/dismissed").status_code == 401
    world["db"].expire_all()
    assert world["db"].get(PaymentRecord, world["a"].id).refund_status == "pending"


def test_refund_of_another_company_is_404_and_untouched(client, world):
    response = client.post(f"/api/v1/orders/refunds/{world['b'].id}/refunded", headers=world["alice"])
    assert response.status_code == 404
    assert client.post(f"/api/v1/orders/refunds/{world['b'].id}/dismissed", headers=world["alice"]).status_code == 404
    world["db"].expire_all()
    assert world["db"].get(PaymentRecord, world["b"].id).refund_status == "pending"


def test_record_without_pending_refund_cannot_be_marked(client, world):
    response = client.post(f"/api/v1/orders/refunds/{world['a_clean'].id}/refunded", headers=world["alice"])
    assert response.status_code == 404
