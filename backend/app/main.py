from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging
import re

import socketio
import structlog

from app.core.config import settings
from app.api.router import api_router
from app.whatsapp.message_queue import message_queue_service
from app.whatsapp.evolution_realtime import evolution_realtime_service
from app.realtime.event_bus import realtime_event_bus
from app.realtime.socket import chat_socket_service

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

_WEBHOOK_TOKEN = re.compile(r"([?&]token=)[^&\s]*")


class RedactWebhookToken(logging.Filter):
    """Mascara `?token=` no access log do uvicorn: o token do webhook vai na URL (ADR 0006)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(_WEBHOOK_TOKEN.sub(r"\1***", a) if isinstance(a, str) else a for a in args)
        return True


logging.getLogger("uvicorn.access").addFilter(RedactWebhookToken())

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema de automação de conversas WhatsApp com IA",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Neuralilux API", environment=settings.ENVIRONMENT)
    await message_queue_service.connect()
    await realtime_event_bus.start(chat_socket_service.emit_realtime_event)
    try:
        await evolution_realtime_service.start()
    except Exception as exc:  # pragma: no cover - defensive startup logging
        logger.error("Failed to start Evolution realtime bridge", error=str(exc))


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Neuralilux API")
    await evolution_realtime_service.stop()
    await realtime_event_bus.stop()
    await message_queue_service.disconnect()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    return {
        "message": "Neuralilux API",
        "version": settings.VERSION,
        "docs": "/docs" if settings.ENVIRONMENT == "development" else None
    }


socket_app = socketio.ASGIApp(
    chat_socket_service.server,
    other_asgi_app=app,
    socketio_path="realtime/socket.io",
)
