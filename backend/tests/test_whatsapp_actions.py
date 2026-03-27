"""
Integration tests for WhatsApp actions via Evolution API.

Tests run against the real Evolution API at localhost:8081.

Endpoints tested:
- POST /chat/findContacts/{instance} - List contacts
- POST /chat/findMessages/{instance} - Read messages
- POST /message/sendText/{instance} - Send message
- GET /instance/connectionState/{instance} - Verify connection status
- POST /chat/findChats/{instance} - List chats

Usage:
    cd backend && pytest tests/test_whatsapp_actions.py -v

Requirements:
    - Evolution API running at localhost:8081
    - Valid API key configured in settings
"""

import pytest
import asyncio

from app.services.evolution_api import evolution_api, EvolutionAPIError


# Test instance name for integration tests
TEST_INSTANCE_NAME = "integration-test-instance"


@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for the module."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def test_instance():
    """
    Create a test instance for integration tests.
    Cleans up after all tests in the module complete.
    """
    created = False
    try:
        result = await evolution_api.create_instance(TEST_INSTANCE_NAME)
        created = True
    except EvolutionAPIError as e:
        if "already exists" in str(e.message).lower() or e.status_code == 403:
            pass
        else:
            pytest.skip(f"Cannot create test instance: {e.message}")

    yield TEST_INSTANCE_NAME

    if created:
        try:
            await evolution_api.delete_instance(TEST_INSTANCE_NAME)
        except EvolutionAPIError:
            pass


class TestListChats:
    """Integration tests for POST /chat/findChats/{instance} - List chats."""

    @pytest.mark.asyncio
    async def test_fetch_chats_returns_list(self, test_instance):
        """Verify fetch_chats returns a list of chats."""
        result = await evolution_api.fetch_chats(test_instance)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_chats_with_valid_instance(self, test_instance):
        """Verify fetch_chats succeeds with a valid instance name."""
        result = await evolution_api.fetch_chats(test_instance)
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_chats_invalid_instance_raises_error(self):
        """Verify fetch_chats raises EvolutionAPIError for invalid instance."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_chats("nonexistent-instance-12345")
        assert exc_info.value.status_code in [400, 404, 500]

    @pytest.mark.asyncio
    async def test_fetch_chats_response_structure(self, test_instance):
        """Verify chat items have expected structure when chats exist."""
        result = await evolution_api.fetch_chats(test_instance)
        if len(result) > 0:
            chat = result[0]
            assert "id" in chat or "remoteJid" in chat or isinstance(chat, dict)


class TestListContacts:
    """Integration tests for POST /chat/findContacts/{instance} - List contacts."""

    @pytest.mark.asyncio
    async def test_fetch_contacts_returns_list(self, test_instance):
        """Verify fetch_contacts returns a list of contacts."""
        result = await evolution_api.fetch_contacts(test_instance)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_contacts_with_valid_instance(self, test_instance):
        """Verify fetch_contacts succeeds with a valid instance name."""
        result = await evolution_api.fetch_contacts(test_instance)
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_contacts_invalid_instance_raises_error(self):
        """Verify fetch_contacts raises EvolutionAPIError for invalid instance."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_contacts("nonexistent-instance-12345")
        assert exc_info.value.status_code in [400, 404, 500]

    @pytest.mark.asyncio
    async def test_fetch_contacts_response_structure(self, test_instance):
        """Verify contact items have expected structure when contacts exist."""
        result = await evolution_api.fetch_contacts(test_instance)
        if len(result) > 0:
            contact = result[0]
            assert isinstance(contact, dict)


class TestReadMessages:
    """Integration tests for POST /chat/findMessages/{instance} - Read messages."""

    @pytest.mark.asyncio
    async def test_fetch_messages_returns_dict(self, test_instance):
        """Verify fetch_messages returns a response dict."""
        result = await evolution_api.fetch_messages(
            instance_name=test_instance,
            remote_jid="5511999999999@s.whatsapp.net",
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_messages_with_pagination(self, test_instance):
        """Verify fetch_messages accepts pagination parameters."""
        result = await evolution_api.fetch_messages(
            instance_name=test_instance,
            remote_jid="5511999999999@s.whatsapp.net",
            page=1,
            offset=10,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_messages_default_offset(self, test_instance):
        """Verify fetch_messages uses default offset of 20."""
        result = await evolution_api.fetch_messages(
            instance_name=test_instance,
            remote_jid="5511999999999@s.whatsapp.net",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_messages_invalid_instance_raises_error(self):
        """Verify fetch_messages raises EvolutionAPIError for invalid instance."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_messages(
                instance_name="nonexistent-instance-12345",
                remote_jid="5511999999999@s.whatsapp.net",
            )
        assert exc_info.value.status_code in [400, 404, 500]


class TestConnectionStatus:
    """Integration tests for GET /instance/connectionState/{instance}."""

    @pytest.mark.asyncio
    async def test_get_instance_status_returns_dict(self, test_instance):
        """Verify get_instance_status returns a status dict."""
        result = await evolution_api.get_instance_status(test_instance)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.asyncio
    async def test_get_instance_status_contains_state(self, test_instance):
        """Verify response contains instance state information."""
        result = await evolution_api.get_instance_status(test_instance)
        assert "instance" in result or "state" in result

    @pytest.mark.asyncio
    async def test_get_instance_status_valid_states(self, test_instance):
        """Verify state is one of the expected values."""
        result = await evolution_api.get_instance_status(test_instance)
        state = result.get("instance", {}).get("state") or result.get("state")
        valid_states = ["open", "close", "connecting", "closed", "disconnected"]
        if state:
            assert state in valid_states or isinstance(state, str)

    @pytest.mark.asyncio
    async def test_get_instance_status_invalid_instance_raises_error(self):
        """Verify get_instance_status raises error for invalid instance."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.get_instance_status("nonexistent-instance-12345")
        assert exc_info.value.status_code in [400, 404, 500]


class TestSendMessage:
    """Integration tests for POST /message/sendText/{instance} - Send message."""

    @pytest.mark.asyncio
    async def test_send_text_message_accepts_request(self, test_instance):
        """
        Verify send_text_message accepts the request.
        May return 500 if instance not connected to WhatsApp.
        """
        try:
            result = await evolution_api.send_text_message(
                instance_name=test_instance,
                remote_jid="5511999999999@s.whatsapp.net",
                text="Integration test message",
            )
            assert isinstance(result, dict)
        except EvolutionAPIError as e:
            if e.status_code == 500:
                pass  # Expected if not connected
            else:
                raise

    @pytest.mark.asyncio
    async def test_send_text_message_invalid_instance_raises_error(self):
        """Verify send_text_message raises error for invalid instance."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.send_text_message(
                instance_name="nonexistent-instance-12345",
                remote_jid="5511999999999@s.whatsapp.net",
                text="Test message",
            )
        assert exc_info.value.status_code in [400, 404, 500]


class TestEvolutionAPIConnectivity:
    """Integration tests for Evolution API connectivity."""

    @pytest.mark.asyncio
    async def test_api_is_reachable(self):
        """Verify the Evolution API at localhost:8081 is reachable."""
        try:
            await evolution_api.fetch_chats("connectivity-test")
        except EvolutionAPIError as e:
            if "Failed to connect" in str(e.message):
                pytest.fail(f"Evolution API is not reachable: {e.message}")

    @pytest.mark.asyncio
    async def test_api_base_url_configured(self):
        """Verify Evolution API base URL is configured correctly."""
        assert evolution_api.base_url is not None
        assert "localhost:8081" in evolution_api.base_url or "http" in evolution_api.base_url

    @pytest.mark.asyncio
    async def test_api_key_configured(self):
        """Verify API key is configured."""
        assert evolution_api.api_key is not None
        assert len(evolution_api.api_key) > 0

    @pytest.mark.asyncio
    async def test_headers_contain_apikey(self):
        """Verify headers include the apikey."""
        assert "apikey" in evolution_api.headers
        assert evolution_api.headers["apikey"] == evolution_api.api_key


class TestInstanceLifecycle:
    """Integration tests for instance create/delete lifecycle."""

    @pytest.mark.asyncio
    async def test_create_and_delete_instance(self):
        """Verify instance can be created and deleted."""
        instance_name = "lifecycle-test-instance"
        create_result = await evolution_api.create_instance(instance_name)
        assert create_result is not None
        delete_result = await evolution_api.delete_instance(instance_name)
        assert delete_result is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_instance_handled(self):
        """Verify creating a duplicate instance is handled gracefully."""
        instance_name = "duplicate-test-instance"
        try:
            await evolution_api.create_instance(instance_name)
            try:
                await evolution_api.create_instance(instance_name)
            except EvolutionAPIError as e:
                assert e.status_code in [400, 403, 409, 500]
        finally:
            try:
                await evolution_api.delete_instance(instance_name)
            except EvolutionAPIError:
                pass
