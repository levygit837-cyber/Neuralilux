from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import socketio
import structlog

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.origin_guard import OriginGuardMiddleware
from app.core.request_id import RequestIdMiddleware
from app.api.router import api_router
from app.schemas.health import HealthResponse, RootResponse
from app.core import http_clients
from app.whatsapp import reimport_guard
from app.whatsapp.message_queue import message_queue_service
from app.whatsapp.evolution_realtime import evolution_realtime_service
from app.realtime.event_bus import realtime_event_bus
from app.realtime.socket import chat_socket_service

configure_logging()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Neuralilux API", environment=settings.ENVIRONMENT)
    await message_queue_service.connect()
    await realtime_event_bus.start(chat_socket_service.emit_realtime_event)
    try:
        await evolution_realtime_service.start()
    except Exception:  # pragma: no cover - defensive startup logging
        logger.exception("Failed to start Evolution realtime bridge")
    yield
    logger.info("Shutting down Neuralilux API")
    await evolution_realtime_service.stop()
    await realtime_event_bus.stop()
    await message_queue_service.disconnect()
    await http_clients.close_all()  # Evolution e Gateways: um cliente por destino, vivo até aqui
    await reimport_guard.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema de automação de conversas WhatsApp com IA",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan,
)

# Adicionado antes do CORS: o CORS fica por fora e a resposta 403 do guarda ainda carrega os cabeçalhos CORS.
app.add_middleware(OriginGuardMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Por último, logo o mais externo: toda resposta (inclusive o 403 do guarda e as do CORS) leva o `X-Request-ID`.
app.add_middleware(RequestIdMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version=settings.VERSION, environment=settings.ENVIRONMENT)


@app.get("/", response_model=RootResponse)
async def root():
    return RootResponse(
        message="Neuralilux API",
        version=settings.VERSION,
        docs="/docs" if settings.ENVIRONMENT == "development" else None,
    )


socket_app = socketio.ASGIApp(
    chat_socket_service.server,
    other_asgi_app=app,
    socketio_path="realtime/socket.io",
)
