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


class TestEvolutionAPIError:
    def test_message_and_code(self):
        err = EvolutionAPIError("test error", 400)
        assert err.message == "test error"
        assert err.status_code == 400
        assert str(err) == "test error"

    def test_default_status_code(self):
        err = EvolutionAPIError("server error")
        assert err.status_code == 500


class TestEvolutionAPIService:
    def test_init_sets_base_url_and_headers(self):
        svc = EvolutionAPIService()
        assert svc.base_url is not None
        assert "apikey" in svc.headers
        assert "Content-Type" in svc.headers


class TestFetchChats:
    """Tests for fetch_chats - POST /chat/findChats/{instance}."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_post_method(self, svc):
        """Verify fetch_chats uses POST (not GET)."""
        route = respx.post(f"{BASE_URL}/chat/findChats/test-instance").mock(
            return_value=httpx.Response(200, json=[{"id": "chat1"}])
        )
        result = await svc.fetch_chats("test-instance")
        assert route.called
        assert route.calls[0].request.method == "POST"

    @respx.mock
    @pytest.mark.asyncio
    async def test_correct_url(self, svc):
        """Verify fetch_chats hits the correct endpoint."""
        route = respx.post(f"{BASE_URL}/chat/findChats/my-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_chats("my-instance")
        assert route.calls[0].request.url.path == "/chat/findChats/my-instance"

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
    async def test_returns_chat_list(self, svc):
        """Verify fetch_chats returns the response JSON."""
        chats = [{"id": "chat1", "name": "Contact 1"}, {"id": "chat2"}]
        respx.post(f"{BASE_URL}/chat/findChats/test-instance").mock(
            return_value=httpx.Response(200, json=chats)
        )
        result = await svc.fetch_chats("test-instance")
        assert result == chats

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
    async def test_uses_post_method(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findMessages/test-instance").mock(
            return_value=httpx.Response(200, json={"messages": {"records": []}})
        )
        await svc.fetch_messages("test-instance", "5511999999999@s.whatsapp.net")
        assert route.calls[0].request.method == "POST"

    @respx.mock
    @pytest.mark.asyncio
    async def test_correct_url(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findMessages/my-instance").mock(
            return_value=httpx.Response(200, json={"messages": {"records": []}})
        )
        await svc.fetch_messages("my-instance", "5511999999999@s.whatsapp.net")
        assert route.calls[0].request.url.path == "/chat/findMessages/my-instance"

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

    @respx.mock
    @pytest.mark.asyncio
    async def test_default_offset(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findMessages/test-instance").mock(
            return_value=httpx.Response(200, json={"messages": {"records": []}})
        )
        await svc.fetch_messages("test-instance", "5511999999999@s.whatsapp.net")
        body = json.loads(route.calls[0].request.content)
        assert body["limit"] == 20

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_messages(self, svc):
        response_data = {"messages": {"total": 5, "records": [{"id": "msg1"}]}}
        respx.post(f"{BASE_URL}/chat/findMessages/test-instance").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        result = await svc.fetch_messages("test-instance", "5511999999999@s.whatsapp.net")
        assert result == response_data


class TestFetchContacts:
    """Tests for fetch_contacts - POST /chat/findContacts/{instance}."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_post_method(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findContacts/test-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_contacts("test-instance")
        assert route.calls[0].request.method == "POST"

    @respx.mock
    @pytest.mark.asyncio
    async def test_correct_url(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findContacts/my-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_contacts("my-instance")
        assert route.calls[0].request.url.path == "/chat/findContacts/my-instance"

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_empty_json_body(self, svc):
        route = respx.post(f"{BASE_URL}/chat/findContacts/test-instance").mock(
            return_value=httpx.Response(200, json=[])
        )
        await svc.fetch_contacts("test-instance")
        assert route.calls[0].request.content == b"{}"

    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_contacts(self, svc):
        contacts = [{"id": "c1", "name": "John"}]
        respx.post(f"{BASE_URL}/chat/findContacts/test-instance").mock(
            return_value=httpx.Response(200, json=contacts)
        )
        result = await svc.fetch_contacts("test-instance")
        assert result == contacts


class TestSendTextMessage:
    """Tests for send_text_message."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_uses_post_method(self, svc):
        route = respx.post(f"{BASE_URL}/message/sendText/test-instance").mock(
            return_value=httpx.Response(200, json={"key": {"id": "msg1"}})
        )
        await svc.send_text_message("test-instance", "5511999999999@s.whatsapp.net", "Hi")
        assert route.calls[0].request.method == "POST"

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
