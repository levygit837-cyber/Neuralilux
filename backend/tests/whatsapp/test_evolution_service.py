"""Unit tests for EvolutionAPIService chat/contact/message endpoints.

Tests verify correct HTTP methods, URLs, and payloads for:
- fetch_chats (POST /chat/findChats/{instance})
- fetch_messages (POST /chat/findMessages/{instance})
- fetch_contacts (POST /chat/findContacts/{instance})
- send_text_message (POST /message/sendText/{instance})
"""

import pytest
import respx
import httpx
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.whatsapp.evolution_client import EvolutionAPIService, EvolutionAPIError


BASE_URL = "http://localhost:8081"
API_KEY = "test-api-key"


@pytest.fixture
def svc():
    """Create an EvolutionAPIService instance with test config."""
    with patch("app.whatsapp.evolution_client.settings") as mock_settings:
        mock_settings.EVOLUTION_API_URL = BASE_URL
        mock_settings.EVOLUTION_API_KEY = API_KEY
        service = EvolutionAPIService()
    return service


class TestFetchChats:
    """Tests for fetch_chats - POST /chat/findChats/{instance}."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_empty_json_body(self, svc):
        """Verify fetch_chats sends an empty JSON body."""
        route = respx.post(f"{BASE_URL}/chat/findChats/test-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_chats("test-instance")
        assert route.calls[0].request.content == b"{}"

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_apikey_header(self, svc):
        """Verify fetch_chats sends the apikey header."""
        route = respx.post(f"{BASE_URL}/chat/findChats/test-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_chats("test-instance")
        assert route.calls[0].request.headers["apikey"] == API_KEY

    @respx.mock
    @pytest.mark.asyncio
    async def test_raises_on_404(self, svc):
        """Verify fetch_chats raises EvolutionAPIError on 404."""
        respx.post(f"{BASE_URL}/chat/findChats/test-instance").mock(
            return_value=httpx.Response(404, json={"error": "Not Found"})
        )
        with pytest.raises(EvolutionAPIError) as exc_info:
            await svc.fetch_chats("test-instance")
        assert exc_info.value.status_code == 404


class TestFetchMessages:
    """Tests for fetch_messages - POST /chat/findMessages/{instance}."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findMessages/test-instance").mock(
            return_value=httpx.Response(200, json={"messages": {"records": []}})
        )
        await svc.fetch_messages(
            "test-instance",
            remote_jid="5511999999999@s.whatsapp.net",
            offset=10,
        )
        body = json.loads(route.calls[0].request.content)
        assert body["where"]["key"]["remoteJid"] == "5511999999999@s.whatsapp.net"
        assert body["limit"] == 10


class TestFetchContacts:
    """Tests for fetch_contacts - POST /chat/findContacts/{instance}."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_empty_json_body(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findContacts/test-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_contacts("test-instance")
        assert route.calls[0].request.content == b"{}"


class TestSendTextMessage:
    """Tests for send_text_message."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_strips_jid_suffix(self, svc):
        route = respx.post(f"{BASE_URL}/message/sendText/test-instance").mock(
            return_value=httpx.Response(200, json={"key": {"id": "msg1"}})
        )
        await svc.send_text_message("test-instance", "5511999999999@s.whatsapp.net", "Hi")
        body = json.loads(route.calls[0].request.content)
        assert body["number"] == "5511999999999"

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_text_and_options(self, svc):
        route = respx.post(f"{BASE_URL}/message/sendText/test-instance").mock(
            return_value=httpx.Response(200, json={"key": {"id": "msg1"}})
        )
        await svc.send_text_message("test-instance", "5511999999999@s.whatsapp.net", "Hello")
        body = json.loads(route.calls[0].request.content)
        assert body["text"] == "Hello"
        assert body["options"]["delay"] == 1200
        assert body["options"]["presence"] == "composing"

    @respx.mock
    @pytest.mark.asyncio
    async def test_raises_on_500(self, svc):
        respx.post(f"{BASE_URL}/message/sendText/test-instance").mock(
            return_value=httpx.Response(500, json={"error": "Server Error"})
        )
        with pytest.raises(EvolutionAPIError) as exc_info:
            await svc.send_text_message("test-instance", "5511999999999@s.whatsapp.net", "Hi")
        assert exc_info.value.status_code == 500


class TestCreateInstance:
    """Tests for create_instance - includes integration field."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_integration_field(self, svc):
        route = respx.post(f"{BASE_URL}/instance/create").mock(
            return_value=httpx.Response(200, json={"instance": {}})
        )
        await svc.create_instance("test-instance")
        body = json.loads(route.calls[0].request.content)
        assert body["integration"] == "WHATSAPP-BAILEYS"

    @respx.mock
    @pytest.mark.asyncio
    async def test_instance_token_is_random_and_never_the_global_api_key(self, svc):
        route = respx.post(f"{BASE_URL}/instance/create").mock(
            return_value=httpx.Response(200, json={"instance": {}})
        )

        await svc.create_instance("inst-a")
        await svc.create_instance("inst-b")

        first, second = (json.loads(call.request.content)["token"] for call in route.calls)
        assert API_KEY not in (first, second)
        assert first != second
        assert len(first) >= 32 and len(second) >= 32
        # a chave global segue autenticando o backend no header, não vai no corpo
        assert route.calls[0].request.headers["apikey"] == API_KEY
        assert API_KEY not in route.calls[0].request.content.decode()


class TestSendPresence:
    """send_presence: POST /chat/sendPresence/{instance} com `number`, `presence` e `delay` (todos obrigatórios na Evolution)."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_posts_composing_with_the_number_and_delay(self, svc):
        route = respx.post(f"{BASE_URL}/chat/sendPresence/test-instance").mock(
            return_value=httpx.Response(201, json={"presence": "composing"})
        )

        await svc.send_presence("test-instance", "5511999999999@s.whatsapp.net", "composing", 20000)

        assert json.loads(route.calls[0].request.content) == {
            "number": "5511999999999",
            "presence": "composing",
            "delay": 20000,
        }

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error_raises_evolution_error(self, svc):
        respx.post(f"{BASE_URL}/chat/sendPresence/test-instance").mock(
            return_value=httpx.Response(500, json={"error": "instância desconectada"})
        )

        with pytest.raises(EvolutionAPIError):
            await svc.send_presence("test-instance", "5511999999999@s.whatsapp.net")

    @pytest.mark.asyncio
    async def test_rejects_a_jid_without_digits(self, svc):
        with pytest.raises(EvolutionAPIError):
            await svc.send_presence("test-instance", "status@broadcast")

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_a_short_timeout_independent_of_the_delay(self, svc):
        route = respx.post(f"{BASE_URL}/chat/sendPresence/test-instance").mock(
            return_value=httpx.Response(201, json={})
        )

        await svc.send_presence("test-instance", "5511999999999@s.whatsapp.net", "composing", 60000)

        timeout = route.calls[0].request.extensions["timeout"]
        assert timeout["read"] is not None and timeout["read"] <= 10

    @respx.mock
    @pytest.mark.asyncio
    async def test_read_timeout_while_evolution_holds_the_delay_counts_as_accepted(self, svc):
        respx.post(f"{BASE_URL}/chat/sendPresence/test-instance").mock(side_effect=httpx.ReadTimeout("delay"))

        assert await svc.send_presence("test-instance", "5511999999999@s.whatsapp.net", "composing", 60000) == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_refused_still_raises(self, svc):
        respx.post(f"{BASE_URL}/chat/sendPresence/test-instance").mock(side_effect=httpx.ConnectError("recusada"))

        with pytest.raises(EvolutionAPIError):
            await svc.send_presence("test-instance", "5511999999999@s.whatsapp.net")
