import base64
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.config import settings
from app.services.message_queue_service import message_queue_service

logger = structlog.get_logger()


def require_webhook_token(token: str = Query("")) -> None:
    """Recusa a chamada sem `?token=` igual a EVOLUTION_WEBHOOK_TOKEN (ADR 0006).

    Token não configurado recusa tudo: um token vazio nunca é uma credencial válida.
    """
    expected = settings.EVOLUTION_WEBHOOK_TOKEN.encode()
    # Bytes, não str: compare_digest levanta TypeError com str não-ASCII.
    if not expected or not hmac.compare_digest(token.encode(), expected):
        logger.warning("Evolution webhook rejected: missing or invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")


router = APIRouter(dependencies=[Depends(require_webhook_token)])


def _convert_bytes_to_base64(obj: Any) -> Any:
    """
    Recursively convert bytes objects to base64 strings for JSON serialization.
    """
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    elif isinstance(obj, dict):
        return {key: _convert_bytes_to_base64(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_bytes_to_base64(item) for item in obj]
    else:
        return obj


def _normalize_event_name(event_name: str | None) -> str | None:
    if not event_name:
        return None
    return event_name.replace("-", ".")


@router.post("/evolution")
@router.post("/evolution/{event_type}")
async def evolution_webhook(request: Request, event_type: str = None):
    """
    Webhook endpoint for Evolution API events

    Receives events from Evolution API such as:
    - messages.upsert (new message)
    - messages.update (message status update)
    - connection.update (connection status)
    - qr.updated (QR code update)
    """
    try:
        payload = await request.json()
        
        # Extract event type from payload or path
        payload_event = payload.get("event")
        final_event = _normalize_event_name(payload_event or event_type)
        
        logger.info(
            "Received Evolution API webhook",
            event_type=final_event,
            path_event=event_type,
            payload_event=payload_event,
            instance=payload.get("instance")
        )

        # Add event to payload if not present
        if final_event:
            payload["event"] = final_event

        # Convert any bytes to base64 strings for JSON serialization
        safe_payload = _convert_bytes_to_base64(payload)

        # Publish webhook event to RabbitMQ for async processing
        await message_queue_service.publish_webhook_event(safe_payload)

        return {"status": "received", "event": final_event}

    except Exception as e:
        logger.error("Error processing webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.get("/evolution/test")
async def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return {"status": "webhook endpoint is accessible"}
