"""
Evolution API Service - Integration with Evolution API for WhatsApp.
Handles QR code, connection status, and disconnection.
"""

import re
import secrets

import httpx
import structlog
from typing import Optional, Dict, Any

from app.core.config import settings

logger = structlog.get_logger()


# Presença "digitando": a Evolution segura a resposta até o fim do `delay`, então só a leitura é curta.
PRESENCE_TIMEOUT = httpx.Timeout(5.0)


def _recipient(remote_jid: str) -> str:
    """`number` da Evolution. Grupo (`@g.us`) e `@lid` sem número real vão com o JID inteiro, que a Evolution
    aceita; os demais, só os dígitos. Os dígitos de um `@lid` não são um telefone e iriam para outra pessoa."""
    if remote_jid.endswith(("@g.us", "@lid")):
        return remote_jid
    return re.sub(r"\D", "", remote_jid.split("@")[0])


class EvolutionAPIError(Exception):
    """Custom exception for Evolution API errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class EvolutionAPIService:
    """Service class for interacting with the Evolution API."""

    def __init__(self):
        self.base_url = settings.EVOLUTION_API_URL
        self.api_key = settings.EVOLUTION_API_KEY
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float | httpx.Timeout = 30.0,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the Evolution API."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    params=params,
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error(
                "Evolution API HTTP error",
                status_code=e.response.status_code,
                url=url,
                detail=e.response.text,
            )
            raise EvolutionAPIError(
                f"Evolution API returned {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("Evolution API request error", url=url, error=str(e))
            raise EvolutionAPIError(
                f"Failed to connect to Evolution API: {str(e)}"
            ) from e

    async def fetch_instances(self) -> list:
        """
        Fetch all WhatsApp instances from Evolution API.
        
        Evolution API v2 endpoint: GET /instance/fetchInstances
        
        Returns list of instance objects with their details.
        """
        logger.info("Fetching all instances from Evolution API")
        result = await self._request(
            "GET",
            "/instance/fetchInstances",
        )
        # Evolution API returns a list directly or wrapped in an object
        if isinstance(result, list):
            return result
        return result.get("instances", result.get("data", [result] if result else []))

    async def get_instance_qrcode(self, instance_name: str) -> Dict[str, Any]:
        """
        Get the QR code for connecting a WhatsApp instance.
        
        Returns dict with 'qrcode' (base64 string) and 'code' (raw QR code data).
        """
        logger.info("Fetching QR code from Evolution API", instance=instance_name)
        result = await self._request(
            "GET",
            f"/instance/connect/{instance_name}",
        )
        return result

    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        """
        Get the connection status of a WhatsApp instance.
        
        Returns dict with 'instance' info including 'state' (open, close, connecting, etc.).
        """
        logger.info("Fetching instance status from Evolution API", instance=instance_name)
        result = await self._request(
            "GET",
            f"/instance/connectionState/{instance_name}",
        )
        return result

    async def disconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        """
        Disconnect a WhatsApp instance.
        
        Returns dict with operation result.
        """
        logger.info("Disconnecting instance from Evolution API", instance=instance_name)
        result = await self._request(
            "DELETE",
            f"/instance/logout/{instance_name}",
        )
        return result

    async def create_instance(self, instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new WhatsApp instance in Evolution API.
        
        A Instance nasce com um token próprio e aleatório, nunca a chave global da Evolution: o token da
        Instance autentica só ela. As chamadas do backend seguem usando a chave global no header `apikey`.

        Returns dict with instance details including QR code if available.
        """
        payload: Dict[str, Any] = {
            "instanceName": instance_name,
            "token": secrets.token_urlsafe(32),
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "rejectCall": False,
            "groupsIgnore": False,
            "alwaysOnline": False,
            "readMessages": False,
            "readStatus": False,
            "syncFullHistory": True,
            "websocket": {
                "enabled": True,
                "events": [
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "CONNECTION_UPDATE",
                    "QRCODE_UPDATED",
                ],
            },
        }
        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "byEvents": True,
                "base64": True,
            }

        logger.info("Creating instance in Evolution API", instance=instance_name)
        result = await self._request(
            "POST",
            "/instance/create",
            data=payload,
        )
        return result

    async def delete_instance(self, instance_name: str) -> Dict[str, Any]:
        """
        Delete a WhatsApp instance from Evolution API.
        
        Returns dict with operation result.
        """
        logger.info("Deleting instance from Evolution API", instance=instance_name)
        result = await self._request(
            "DELETE",
            f"/instance/delete/{instance_name}",
        )
        return result


    async def fetch_chats(self, instance_name: str) -> Dict[str, Any]:
        """
        Fetch all chats (conversations) for a WhatsApp instance.
        
        Evolution API v2.3.7+ requires POST /chat/findChats/{instance}
        with an empty JSON body.
        
        Returns dict with array of chats from Evolution API.
        """
        logger.info("Fetching chats from Evolution API", instance=instance_name)
        result = await self._request(
            "POST",
            f"/chat/findChats/{instance_name}",
            data={},
        )
        return result

    async def fetch_messages(
        self,
        instance_name: str,
        remote_jid: str,
        page: int = 1,
        offset: int = 20,
    ) -> Dict[str, Any]:
        """Histórico de um chat (`remote_jid`). `page` é ignorado: a Evolution usa só `limit`."""
        logger.info(
            "Fetching messages from Evolution API",
            instance=instance_name,
            remote_jid=remote_jid,
        )
        payload = {
            "where": {
                "key": {
                    "remoteJid": remote_jid,
                }
            },
            "limit": offset,
        }
        result = await self._request(
            "POST",
            f"/chat/findMessages/{instance_name}",
            data=payload,
        )
        return result

    async def fetch_contacts(
        self,
        instance_name: str,
    ) -> Dict[str, Any]:
        """
        Fetch all contacts for a WhatsApp instance.

        Evolution API v2.3.7+ uses POST /chat/findContacts/{instance}
        with an empty JSON body.

        Args:
            instance_name: The Evolution API instance name.

        Returns dict with array of contacts.
        """
        logger.info(
            "Fetching contacts from Evolution API",
            instance=instance_name,
        )
        result = await self._request(
            "POST",
            f"/chat/findContacts/{instance_name}",
            data={},
        )
        return result

    async def send_presence(
        self, instance_name: str, remote_jid: str, presence: str = "composing", delay_ms: int = 0
    ) -> Dict[str, Any]:
        """Mostra `presence` (ex.: "composing" = digitando) ao Contact.

        A Evolution só responde depois de `delay_ms`, mas já mostrou a presença ao aceitar o pedido. Por isso o
        timeout de leitura é curto e independente do `delay`, e estourá-lo vale como "aceito": o `delay` pode passar
        do timeout padrão de 30 s sem derrubar a presença. Conexão recusada e erro HTTP continuam levantando.
        """
        number = _recipient(remote_jid)
        if not instance_name or not number:
            raise EvolutionAPIError("instance_name and a numeric remote_jid are required", status_code=400)
        try:
            return await self._request(
                "POST",
                f"/chat/sendPresence/{instance_name}",
                data={"number": number, "presence": presence, "delay": delay_ms},
                timeout=PRESENCE_TIMEOUT,
            )
        except EvolutionAPIError as error:
            if isinstance(error.__cause__, httpx.ReadTimeout):
                return {}
            raise

    async def send_text_message(
        self,
        instance_name: str,
        remote_jid: str,
        text: str,
    ) -> Dict[str, Any]:
        """
        Send a text message via WhatsApp.
        
        Args:
            instance_name: The Evolution API instance name.
            remote_jid: WhatsApp contact JID (e.g., 5511999999999@s.whatsapp.net).
            text: The text message content.
        
        Returns dict with message details including key.id (message_id).
        
        Raises:
            EvolutionAPIError: If validation fails or API returns error.
        """
        logger.info(
            "Sending text message via Evolution API",
            instance=instance_name,
            remote_jid=remote_jid,
        )
        
        # Validate inputs
        if not instance_name or not instance_name.strip():
            raise EvolutionAPIError("instance_name is required", status_code=400)
        
        if not remote_jid or not remote_jid.strip():
            raise EvolutionAPIError("remote_jid is required", status_code=400)
        
        if not text or not text.strip():
            raise EvolutionAPIError("text message is required", status_code=400)
        
        number = _recipient(remote_jid)
        
        if not number:
            raise EvolutionAPIError(
                f"Invalid remote_jid format: {remote_jid}",
                status_code=400
            )
        
        payload = {
            "number": number,
            "text": text.strip(),
            "options": {
                "delay": 1200,
                "presence": "composing",
            },
        }
        
        result = await self._request(
            "POST",
            f"/message/sendText/{instance_name}",
            data=payload,
        )
        
        # Validate response contains expected fields
        if not isinstance(result, dict):
            raise EvolutionAPIError(
                f"Invalid response from Evolution API: expected dict, got {type(result).__name__}",
                status_code=500
            )
        
        # Check for success indicator - Evolution API returns key.id on success
        key = result.get("key")
        if key and isinstance(key, dict) and key.get("id"):
            logger.info(
                "Message sent successfully",
                instance=instance_name,
                message_id=key.get("id"),
            )
            return result
        
        # Some versions return different format - check for success flag or message id
        if result.get("success") or result.get("id") or result.get("messageId"):
            logger.info(
                "Message sent successfully (alternate format)",
                instance=instance_name,
            )
            return result
        
        # Check for error in response
        if "error" in result or result.get("status") == "error":
            error_msg = result.get("error") or result.get("message") or "Unknown error"
            raise EvolutionAPIError(
                f"Evolution API returned error: {error_msg}",
                status_code=500
            )
        
        # Return result anyway - let caller decide
        logger.warning(
            "Message sent but response format unclear",
            instance=instance_name,
            response_keys=list(result.keys()) if isinstance(result, dict) else "N/A",
        )
        return result


# Singleton instance
evolution_api = EvolutionAPIService()
