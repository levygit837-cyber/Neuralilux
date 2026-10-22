"""O painel de Orders (#34) vista pelo Agent: o que a Company move muda o que o Contact pode fazer e o que ele ouve."""
import pytest
from changes_helpers import closed_order
from pack_helpers import call, payload

from app.models import Conversation, CustomerOrder, Ticket
from tests.access_helpers import fake_text_sender, make_user, user_id

pytestmark = pytest.mark.asyncio


@pytest.fixture
def alice(client, db, world):
    headers = make_user(client, db, "alice@example.com", company=world.company)
    world.instance.owner_id = user_id(db, "alice@example.com")
    db.commit()
    return headers


@pytest.fixture
def status_pedido(world):
    from app.packs.catalog_orders.pack import CatalogOrdersPack
    from pack_helpers import tool_named

    return tool_named(CatalogOrdersPack().tools(), "status_pedido")


def move(client, alice, order, status):
    response = client.post(f"/api/v1/orders/{order.id}/status", json={"status": status}, headers=alice)
    assert response.status_code == 200, response.text
    return response


async def test_after_the_company_starts_preparing_the_contact_can_no_longer_cancel_or_alter_and_is_offered_handoff(
    monkeypatch, client, world, pedido, alice
):
    fake_text_sender(monkeypatch)
    order = await closed_order(world, pedido)
    move(client, alice, order, "in_production")

    for action in ("cancelar_pedido", "alterar_pedido"):
        result = await call(pedido, world.ctx, acao=action)
        assert result.is_error
        assert "em preparo" in result.content and "transferir_atendente" in result.content

    world.db.expire_all()
    assert world.db.get(CustomerOrder, order.id).status == "in_production"
    assert world.db.query(Ticket).count() == 0
    assert world.db.get(Conversation, world.conversation.id).human_in_loop is False


async def test_whats_my_order_follows_each_move_the_company_makes(monkeypatch, client, world, pedido, status_pedido, alice):
    fake_text_sender(monkeypatch)
    order = await closed_order(world, pedido)
    assert payload(await call(status_pedido, world.ctx))["pedido"]["status_descricao"] == "recebido, aguardando preparo"

    for target, label in [("in_production", "em preparo"), ("sent", "saiu para entrega"), ("delivered", "entregue")]:
        move(client, alice, order, target)
        world.db.expire_all()
        view = payload(await call(status_pedido, world.ctx))["pedido"]
        assert view["status"] == target and view["status_descricao"] == label


async def test_order_the_company_cancelled_is_reported_as_cancelled_to_the_contact(
    monkeypatch, client, world, pedido, status_pedido, alice
):
    fake_text_sender(monkeypatch)
    order = await closed_order(world, pedido)
    move(client, alice, order, "cancelled")

    world.db.expire_all()
    assert payload(await call(status_pedido, world.ctx))["pedido"]["status_descricao"] == "cancelado"
    assert (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error  # já cancelado: não cancela de novo
