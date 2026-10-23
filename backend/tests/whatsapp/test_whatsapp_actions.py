"""
e2e do client da Evolution API contra a Evolution real (`EVOLUTION_API_URL`, padrão localhost:8081).

Só leitura: lista chats e contatos, lê mensagens e consulta o estado da conexão da instância existente
(`E2E_EVOLUTION_INSTANCE`, padrão `Macedos`). Nada cria nem apaga instância e nenhuma mensagem é enviada:
o único envio é para uma instância que não existe e tem de falhar antes de chegar ao WhatsApp.

Roda só com `RUN_E2E=1` (ver `tests/conftest.py`), que também deixa de forçar o SQLite; estes testes não
tocam o banco, então aponte `DATABASE_URL` para um SQLite descartável.

Uso (de `backend/`):

    RUN_E2E=1 DATABASE_URL=sqlite:////tmp/e2e-actions.db EVOLUTION_API_KEY=<chave> \\
        ./venv/bin/python -m pytest tests/whatsapp/test_whatsapp_actions.py -v -p no:cacheprovider

Requisitos: Evolution no ar, `EVOLUTION_API_KEY` válida e a instância (`Macedos`) cadastrada nela.
"""

import os

import pytest

from app.whatsapp.evolution_client import evolution_api, EvolutionAPIError

# Fala com a Evolution API real; roda só com RUN_E2E=1.
pytestmark = pytest.mark.e2e

INSTANCE_NAME = os.environ.get("E2E_EVOLUTION_INSTANCE", "Macedos")
MISSING_INSTANCE = "nonexistent-instance-12345"
REMOTE_JID = "5511999999999@s.whatsapp.net"


@pytest.fixture(scope="module")
def test_instance_name():
    """Nome da instância real usada nas leituras."""
    return INSTANCE_NAME


class TestListChats:
    """POST /chat/findChats/{instance}."""

    @pytest.mark.asyncio
    async def test_fetch_chats_returns_list(self, test_instance_name):
        result = await evolution_api.fetch_chats(test_instance_name)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_chats_invalid_instance_raises_error(self):
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_chats(MISSING_INSTANCE)
        assert exc_info.value.status_code in [400, 404, 500]


class TestListContacts:
    """POST /chat/findContacts/{instance}."""

    @pytest.mark.asyncio
    async def test_fetch_contacts_returns_list(self, test_instance_name):
        result = await evolution_api.fetch_contacts(test_instance_name)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_contacts_invalid_instance_raises_error(self):
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_contacts(MISSING_INSTANCE)
        assert exc_info.value.status_code in [400, 404, 500]


class TestReadMessages:
    """POST /chat/findMessages/{instance}."""

    @pytest.mark.asyncio
    async def test_fetch_messages_returns_dict(self, test_instance_name):
        result = await evolution_api.fetch_messages(instance_name=test_instance_name, remote_jid=REMOTE_JID)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.asyncio
    async def test_fetch_messages_invalid_instance_raises_error(self):
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.fetch_messages(instance_name=MISSING_INSTANCE, remote_jid=REMOTE_JID)
        assert exc_info.value.status_code in [400, 404, 500]


class TestConnectionStatus:
    """GET /instance/connectionState/{instance}."""

    @pytest.mark.asyncio
    async def test_get_instance_status_returns_dict(self, test_instance_name):
        result = await evolution_api.get_instance_status(test_instance_name)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.asyncio
    async def test_get_instance_status_contains_state(self, test_instance_name):
        result = await evolution_api.get_instance_status(test_instance_name)
        assert "instance" in result or "state" in result

    @pytest.mark.asyncio
    async def test_get_instance_status_invalid_instance_raises_error(self):
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.get_instance_status(MISSING_INSTANCE)
        assert exc_info.value.status_code in [400, 404, 500]


class TestSendMessage:
    """POST /message/sendText/{instance}: só o caso de erro, para uma instância que não existe."""

    @pytest.mark.asyncio
    async def test_send_text_message_invalid_instance_raises_error(self):
        with pytest.raises(EvolutionAPIError) as exc_info:
            await evolution_api.send_text_message(
                instance_name=MISSING_INSTANCE,
                remote_jid=REMOTE_JID,
                text="Test message",
            )
        assert exc_info.value.status_code in [400, 404, 500]
