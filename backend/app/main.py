from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import socketio
import structlog

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.message_queue_service import message_queue_service
from app.services.evolution_realtime import evolution_realtime_service
from app.services.realtime_event_bus import realtime_event_bus
from app.services.socket_service import chat_socket_service

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

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
    message_queue_service.connect()
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
    message_queue_service.disconnect()


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
