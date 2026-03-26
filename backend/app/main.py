from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import structlog

from app.core.config import settings
from app.api.v1.router import api_router

# Configure structured logging
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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Neuralilux API", environment=settings.ENVIRONMENT)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Neuralilux API")


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
