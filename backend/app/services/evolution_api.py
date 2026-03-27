"""
Evolution API Service - Integration with Evolution API for WhatsApp.
Handles QR code, connection status, and disconnection.
"""

import httpx
import structlog
from typing import Optional, Dict, Any

from app.core.config import settings

logger = structlog.get_logger()


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
    ) -> Dict[str, Any]:
        """Make an HTTP request to the Evolution API."""
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            )

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
        
        Returns dict with instance details including QR code if available.
        """
        payload: Dict[str, Any] = {
            "instanceName": instance_name,
            "token": self.api_key,
            "qrcode": True,
        }
        if webhook_url:
            payload["webhook"] = webhook_url
            payload["webhook_by_events"] = True

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
        
        Returns dict with array of chats from Evolution API.
        """
        logger.info("Fetching chats from Evolution API", instance=instance_name)
        result = await self._request(
            "GET",
            f"/chat/findChats/{instance_name}",
        )
        return result

    async def fetch_messages(
        self,
        instance_name: str,
        remote_jid: str,
        page: int = 1,
        offset: int = 20,
    ) -> Dict[str, Any]:
        """
        Fetch message history for a specific chat.
        
        Args:
            instance_name: The Evolution API instance name.
            remote_jid: WhatsApp contact JID (e.g., 5511999999999@s.whatsapp.net).
            page: Page number for pagination.
            offset: Number of messages per page.
        
        Returns dict with array of messages.
        """
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
        """
        logger.info(
            "Sending text message via Evolution API",
            instance=instance_name,
            remote_jid=remote_jid,
        )
        payload = {
            "number": remote_jid.split("@")[0] if "@" in remote_jid else remote_jid,
            "text": text,
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
        return result


# Singleton instance
evolution_api = EvolutionAPIService()