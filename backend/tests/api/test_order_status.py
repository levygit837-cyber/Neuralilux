"""Painel de Orders da Company (#34): lista escopada, máquina de status, aviso ao Contact e estorno do Pix."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.models import CustomerOrder, Message, PaymentRecord
from tests.access_helpers import fake_text_sender, make_company, make_instance, make_user
from tests.order_helpers import NOW, make_order


@pytest.fixture
def query_counter(db):
    """Conta os statements que chegam ao banco dentro do bloco `with`."""
    from contextlib import contextmanager

    from sqlalchemy import event

    from tests.conftest import engine

    @contextmanager
    def count():
        statements: list[str] = []

        def record(_conn, _cursor, statement, *_rest):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            yield statements
        finally:
            event.remove(engine, "before_cursor_execute", record)

    return count


@pytest.fixture
def world(client, db):
    company_a, company_b = make_company(db, "Empresa A"), make_company(db, "Empresa B")
    alice = make_user(client, db, "alice@example.com", company=company_a)
    bob = make_user(client, db, "bob@example.com", company=company_b)
    inst_a = make_instance(db, "inst-a", "alice@example.com", company_a)
    return {
        "alice": alice, "bob": bob, "db": db, "inst_a": inst_a,
        "received": make_order(db, inst_a, "A-1", "closed", opened_at=NOW - timedelta(hours=3)),
        "cooking": make_order(db, inst_a, "A-2", "in_production", opened_at=NOW - timedelta(hours=2)),
        "on_the_way": make_order(db, inst_a, "A-3", "sent", opened_at=NOW - timedelta(hours=1)),
        "done": make_order(db, inst_a, "A-4", "delivered", opened_at=NOW),
        "cancelled": make_order(db, inst_a, "A-5", "cancelled", opened_at=NOW - timedelta(hours=4)),
        "assembling": make_order(db, inst_a, "A-6", "open", confirmed=False),
        "abandoned": make_order(db, inst_a, "A-7", "abandoned", confirmed=False),
        "reopened": make_order(db, inst_a, "A-8", "ready_for_confirmation", opened_at=NOW - timedelta(hours=5)),
        "other": make_order(db, make_instance(db, "inst-b2", "bob@example.com", company_b), "B-1", "closed"),
    }


@pytest.fixture
def sender(monkeypatch):
    return fake_text_sender(monkeypatch)


def move(client, world, order, status, who="alice"):
    return client.post(f"/api/v1/orders/{order.id}/status", json={"status": status}, headers=world[who])


def stored_messages(world, order):
    world["db"].expire_all()
    return world["db"].query(Message).filter_by(conversation_id=order.conversation_id).all()


def status_of(world, order):
    world["db"].expire_all()
    return world["db"].get(CustomerOrder, order.id).status


# ---------- lista ----------


def test_panel_lists_only_active_confirmed_orders_by_default(client, world):
    body = client.get("/api/v1/orders", headers=world["alice"]).json()

    assert {o["order_number"] for o in body["orders"]} == {"A-1", "A-2", "A-3", "A-8"}  # sem entregue/cancelado, montagem e abandonado
    assert body["total"] == 4


def test_panel_row_carries_what_the_company_needs_to_act(client, world):
    rows = {o["order_number"]: o for o in client.get("/api/v1/orders?status=all", headers=world["alice"]).json()["orders"]}

    row = rows["A-1"]
    assert row["id"] == world["received"].id and row["status"] == "closed"
    assert row["customer_name"] == "Maria" and row["total_amount"] == 95.0 and row["payment_method"] == "dinheiro"
    assert row["items"] == [{"name": "Pizza Toscana", "quantity": 2, "subtotal": 90.0}]
    assert row["allowed_transitions"] == ["in_production", "cancelled"]
    assert rows["A-2"]["allowed_transitions"] == ["sent", "cancelled"]
    assert rows["A-3"]["allowed_transitions"] == ["delivered"]
    assert rows["A-4"]["allowed_transitions"] == [] and rows["A-5"]["allowed_transitions"] == []


def test_order_being_altered_is_shown_as_such_and_cannot_be_moved(client, world):
    row = next(o for o in client.get("/api/v1/orders", headers=world["alice"]).json()["orders"] if o["order_number"] == "A-8")

    assert row["being_altered"] is True and row["allowed_transitions"] == []
    assert "alteração" in row["status_label"]


def test_panel_flags_orders_with_a_pix_to_refund(client, db, world):
    pending = make_order(db, world["inst_a"], "A-9", "cancelled")
    db.add(PaymentRecord(
        order_id=pending.id, conversation_id=pending.conversation_id, amount=Decimal("95.00"), pix_key="k@pix",
        payment_method="pix", status="cancelled", refund_status="pending",
    ))
    db.commit()

    rows = {o["order_number"]: o for o in client.get("/api/v1/orders?status=all", headers=world["alice"]).json()["orders"]}

    assert rows["A-9"]["refund_status"] == "pending" and rows["A-1"]["refund_status"] is None


def numbers(client, world, query):
    body = client.get(f"/api/v1/orders?{query}", headers=world["alice"]).json()
    return [o["order_number"] for o in body["orders"]], body["total"]


def test_status_filter_splits_active_from_finished_and_all_lists_everything(client, world):
    assert numbers(client, world, "status=active") == (["A-3", "A-2", "A-1", "A-8"], 4)
    assert numbers(client, world, "status=done") == (["A-4", "A-5"], 2)
    assert numbers(client, world, "status=all") == (["A-4", "A-3", "A-2", "A-1", "A-5", "A-8"], 6)


def test_unknown_status_filter_is_422(client, world):
    assert client.get("/api/v1/orders?status=banana", headers=world["alice"]).status_code == 422


def test_offset_and_limit_page_through_the_filtered_list_with_the_total(client, world):
    assert numbers(client, world, "status=all&limit=2") == (["A-4", "A-3"], 6)
    assert numbers(client, world, "status=all&limit=2&offset=2") == (["A-2", "A-1"], 6)
    assert numbers(client, world, "status=all&limit=2&offset=4") == (["A-5", "A-8"], 6)
    assert numbers(client, world, "status=all&limit=2&offset=6") == ([], 6)
    assert client.get("/api/v1/orders?offset=-1", headers=world["alice"]).status_code == 422


def test_old_received_order_is_still_listed_behind_many_newer_delivered_ones(client, db, world):
    for index in range(12):
        make_order(db, world["inst_a"], f"D-{index}", "delivered", opened_at=NOW + timedelta(hours=1 + index))

    listed, total = numbers(client, world, "limit=3")  # padrão: ativos

    assert listed == ["A-3", "A-2", "A-1"] and total == 4  # o `closed` mais antigo não some atrás dos 12 entregues
    assert numbers(client, world, "limit=3&offset=3") == (["A-8"], 4)


def test_listing_runs_the_same_number_of_queries_however_many_orders_there_are(client, db, world, query_counter):
    with query_counter() as few:
        client.get("/api/v1/orders?status=all", headers=world["alice"])
    for index in range(8):
        make_order(db, world["inst_a"], f"P-{index}", "cancelled", pix="cancelled", opened_at=NOW - timedelta(days=1 + index))

    with query_counter() as many:
        body = client.get("/api/v1/orders?status=all", headers=world["alice"]).json()

    assert len(body["orders"]) == 14 and len(many) == len(few)  # sem um SELECT de estorno por linha


def test_panel_requires_a_token(client, world):
    assert client.get("/api/v1/orders").status_code == 401
    assert client.post(f"/api/v1/orders/{world['received'].id}/status", json={"status": "in_production"}).status_code == 401
    assert status_of(world, world["received"]) == "closed"


# ---------- transições ----------


def test_company_walks_an_order_to_delivered_and_the_contact_hears_each_step(client, world, sender):
    order = world["received"]
    for target, expected in [
        ("in_production", "em preparo"),
        ("sent", "saiu para entrega"),
        ("delivered", "foi entregue"),
    ]:
        response = move(client, world, order, target)
        assert response.status_code == 200, response.text
        assert response.json()["order"]["status"] == target
        assert response.json()["notification"] == {"sent": True, "error": None}
        assert status_of(world, order) == target
        assert expected in stored_messages(world, order)[-1].content

    messages = stored_messages(world, order)
    assert len(messages) == 3
    assert all(m.is_from_me and m.direction == "outgoing" and "A-1" in m.content for m in messages)
    assert [call.kwargs["remote_jid"] for call in sender.await_args_list] == [order.remote_jid] * 3


@pytest.mark.parametrize(
    ("order_key", "target"),
    [
        ("done", "in_production"),   # entregue não volta
        ("done", "cancelled"),
        ("received", "sent"),        # não pula o preparo
        ("received", "delivered"),
        ("cooking", "in_production"),  # repetir o mesmo status não reenvia o aviso
        ("cooking", "delivered"),
        ("on_the_way", "cancelled"),   # já saiu: só por Handoff
        ("on_the_way", "in_production"),
        ("cancelled", "in_production"),
        ("cancelled", "cancelled"),
    ],
)
def test_invalid_transitions_are_refused_without_side_effects(client, world, sender, order_key, target):
    order = world[order_key]
    before = status_of(world, order)

    response = move(client, world, order, target)

    assert response.status_code == 409
    assert status_of(world, order) == before
    assert stored_messages(world, order) == [] and sender.await_count == 0


def test_order_being_altered_refuses_every_move(client, world, sender):
    for target in ("in_production", "sent", "delivered", "cancelled"):
        response = move(client, world, world["reopened"], target)
        assert response.status_code == 409
        assert "alteração" in response.json()["detail"]
    assert status_of(world, world["reopened"]) == "ready_for_confirmation" and sender.await_count == 0


def test_unknown_target_status_is_rejected(client, world, sender):
    for target in ("closed", "abandoned", "banana"):
        assert move(client, world, world["received"], target).status_code == 422
    assert status_of(world, world["received"]) == "closed" and sender.await_count == 0


def test_order_of_another_company_is_404_and_untouched(client, world, sender):
    response = move(client, world, world["other"], "in_production")

    assert response.status_code == 404
    assert status_of(world, world["other"]) == "closed" and sender.await_count == 0


def test_order_that_does_not_exist_is_404(client, world):
    response = client.post("/api/v1/orders/nope/status", json={"status": "in_production"}, headers=world["alice"])
    assert response.status_code == 404


# ---------- aviso ao Contact ----------


def test_failure_to_notify_keeps_the_new_status_and_is_reported(monkeypatch, client, world):
    fake_text_sender(monkeypatch, fail=RuntimeError("evolution fora do ar"))

    response = move(client, world, world["received"], "in_production")

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["status"] == "in_production"
    assert body["notification"]["sent"] is False and body["notification"]["error"]
    assert status_of(world, world["received"]) == "in_production"
    assert stored_messages(world, world["received"]) == []


# ---------- cancelamento pela Company ----------


def test_company_cancelling_a_dinheiro_order_tells_the_contact_without_mentioning_refund(client, world, sender):
    response = move(client, world, world["received"], "cancelled")

    assert response.status_code == 200 and response.json()["order"]["status"] == "cancelled"
    order = world["db"].get(CustomerOrder, world["received"].id)
    assert order.cancelled_at is not None
    text = stored_messages(world, order)[-1].content
    assert "cancelado" in text and "A-1" in text and "estorno" not in text


@pytest.mark.parametrize(("pix_status", "refund"), [("paid", "pending"), ("pending", "verify")])
def test_company_cancelling_a_pix_order_flags_the_refund_like_the_contacts_cancel(
    client, db, world, sender, pix_status, refund
):
    order = make_order(db, world["inst_a"], "A-10", "in_production", pix=pix_status)

    response = move(client, world, order, "cancelled")

    assert response.status_code == 200
    record = db.query(PaymentRecord).filter_by(order_id=order.id).one()
    db.refresh(record)
    assert record.status == "cancelled" and record.refund_status == refund and record.refund_flagged_at is not None
    refunds = client.get("/api/v1/orders/refunds", headers=world["alice"]).json()["refunds"]
    assert [r["order_number"] for r in refunds] == ["A-10"]
    assert "estorno" in stored_messages(world, order)[-1].content
    row = next(o for o in client.get("/api/v1/orders?status=all", headers=world["alice"]).json()["orders"] if o["order_number"] == "A-10")
    assert row["refund_status"] == refund
