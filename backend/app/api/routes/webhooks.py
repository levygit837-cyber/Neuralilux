import hmac

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.config import settings
from app.schemas.webhook import WebhookReceived, WebhookTestResponse
from app.whatsapp.message_queue import message_queue_service
from app.whatsapp.webhook_parser import webhook_message_ids

logger = structlog.get_logger()


def require_webhook_token(token: str = Query("")) -> str | None:
    """Recusa a chamada sem `?token=` igual a EVOLUTION_WEBHOOK_TOKEN (ADR 0006).

    Token não configurado recusa tudo: um token vazio nunca é uma credencial válida.

    Com `WEBHOOK_BY_EVENTS=true` a Evolution anexa `/<evento>` ao fim da URL global, e como a URL termina na
    query string o sufixo cai dentro do valor do token (`X/messages-upsert`). Só a parte antes da primeira `/`
    é comparada; o resto é devolvido como evento, para o caso de o payload não trazer `event`.
    """
    secret, _, event_suffix = token.partition("/")
    expected = settings.EVOLUTION_WEBHOOK_TOKEN.encode()
    # Bytes, não str: compare_digest levanta TypeError com str não-ASCII.
    if not expected or not hmac.compare_digest(secret.encode(), expected):
        logger.warning("Evolution webhook rejected: missing or invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")
    return event_suffix or None


router = APIRouter(dependencies=[Depends(require_webhook_token)])


def _normalize_event_name(event_name: str | None) -> str | None:
    if not event_name:
        return None
    return event_name.replace("-", ".")


@router.post("/evolution", response_model=WebhookReceived)
@router.post("/evolution/{event_type}", response_model=WebhookReceived)
async def evolution_webhook(
    request: Request,
    event_type: str | None = None,
    token_event: str | None = Depends(require_webhook_token),  # mesma instância já resolvida pelo router
):
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
        
        # Evento: payload.event, senão o path, senão o sufixo que a Evolution anexou ao token
        payload_event = payload.get("event")
        final_event = _normalize_event_name(payload_event or event_type or token_event)
        
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

        # Publish webhook event to RabbitMQ for async processing (bytes viram base64 uma vez, na fila)
        published = await message_queue_service.publish_webhook_event(payload)

    except Exception:
        logger.exception("Error processing webhook")
        raise HTTPException(status_code=500, detail="Error processing webhook")

    if not published:
        # 503 (e não 200) para a Evolution saber que o evento não foi aceito; ver docs/agents/evolution-data-formats.md.
        logger.error(
            "Evolution webhook event lost: publish to RabbitMQ failed",
            event_type=final_event,
            instance=payload.get("instance"),
            message_ids=webhook_message_ids(payload),
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Event queue unavailable")

    return WebhookReceived(status="received", event=final_event)


@router.get("/evolution/test", response_model=WebhookTestResponse)
def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return WebhookTestResponse(status="webhook endpoint is accessible")
