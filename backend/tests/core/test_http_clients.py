"""Um `httpx.AsyncClient` por destino, vivo durante o processo (#93): Evolution, cada Gateway, ciclo de vida."""
import httpx
import pytest
import respx

from app.core import http_clients
from app.llm.client import GatewayMessagesClient
from app.whatsapp.evolution_client import evolution_api

pytestmark = pytest.mark.asyncio

GATEWAY_A = "http://gateway-a.test"
GATEWAY_B = "http://gateway-b.test"


@pytest.fixture
def created(monkeypatch):
    """Registro dos `AsyncClient` criados durante o teste, com o registry de destinos zerado."""
    monkeypatch.setattr(http_clients, "_clients", {})
    clients: list[httpx.AsyncClient] = []
    real_init = httpx.AsyncClient.__init__

    def counting_init(self, *args, **kwargs):
        clients.append(self)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", counting_init)
    return clients


@respx.mock
async def test_evolution_calls_share_one_client(created):
    respx.get(f"{evolution_api.base_url}/instance/connectionState/a").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{evolution_api.base_url}/instance/connectionState/b").mock(return_value=httpx.Response(200, json={}))

    for name in ("a", "b", "a", "b", "a"):
        await evolution_api.get_instance_status(name)

    assert len(created) == 1
    assert http_clients.get(f"evolution:{evolution_api.base_url}") is created[0]


@respx.mock
async def test_each_gateway_gets_its_own_client_shared_by_every_call_to_it(created):
    for root in (GATEWAY_A, GATEWAY_B):
        respx.get(f"{root}/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "m"}]}))

    for _ in range(3):
        assert await GatewayMessagesClient(GATEWAY_A, "k").list_models() == ["m"]
    assert await GatewayMessagesClient(GATEWAY_B, "k").list_models() == ["m"]
    assert await GatewayMessagesClient(f"{GATEWAY_A}/", "k").list_models() == ["m"]  # mesma raiz, mesmo cliente

    assert len(created) == 2


async def test_evolution_and_gateway_never_share_a_client(created):
    assert http_clients.get("evolution:http://x") is not http_clients.get("gateway:http://x")
    assert http_clients.get("evolution:http://x") is http_clients.get("evolution:http://x")


async def test_close_all_closes_every_client_and_a_later_get_opens_a_new_one(created):
    first = http_clients.get("gateway:http://x")

    await http_clients.close_all()
    await http_clients.close_all()  # idempotente

    assert first.is_closed
    second = http_clients.get("gateway:http://x")
    assert second is not first and not second.is_closed
    await http_clients.close_all()


async def test_api_lifespan_closes_the_shared_clients_on_shutdown(created, monkeypatch):
    from unittest.mock import AsyncMock

    from app import main

    for service in (main.message_queue_service, main.realtime_event_bus, main.evolution_realtime_service):
        for method in ("connect", "disconnect", "start", "stop"):
            if hasattr(service, method):
                monkeypatch.setattr(service, method, AsyncMock())
    client = http_clients.get("evolution:http://x")

    async with main.lifespan(main.app):
        assert not client.is_closed

    assert client.is_closed
