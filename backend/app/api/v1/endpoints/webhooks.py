from fastapi import APIRouter, Request, HTTPException
import structlog

from app.services.message_queue_service import message_queue_service

router = APIRouter()
logger = structlog.get_logger()


@router.post("/evolution")
async def evolution_webhook(request: Request):
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
        event_type = payload.get("event")
        
        logger.info(
            "Received Evolution API webhook",
            event_type=event_type,
            instance=payload.get("instance")
        )

        # Publish webhook event to RabbitMQ for async processing
        message_queue_service.publish_webhook_event(payload)

        return {"status": "received", "event": event_type}

    except Exception as e:
        logger.error("Error processing webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.get("/evolution/test")
async def test_webhook():
    """Test endpoint to verify webhook is accessible"""
    return {"status": "webhook endpoint is accessible"}
