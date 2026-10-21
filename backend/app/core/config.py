from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


_INSECURE_SECRET_KEY_PREFIX = "change-me-in-production"
_INSECURE_WEBHOOK_TOKEN_PREFIX = "change-me"


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Neuralilux"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+psycopg://neuralilux:neuralilux_password@localhost:5434/neuralilux"

    # Redis
    REDIS_URL: str = "redis://:redis_password@localhost:6380/0"

    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8081"
    EVOLUTION_API_KEY: str = ""  # sem default: vem do ambiente
    EVOLUTION_WEBHOOK_TOKEN: str = ""  # ?token= do webhook (ADR 0006); vazio recusa toda chamada
    EVOLUTION_WEBSOCKET_ENABLED: bool = False

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://neuralilux:rabbitmq_password@localhost:5672/neuralilux"
    RABBITMQ_PREFETCH: int = 8  # mensagens simultâneas por consumer

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Gateway local "Kiro-backend" (semeado na primeira execucao; depois editavel pela API/UI)
    KIRO_GATEWAY_URL: str = "http://localhost:5580"  # raiz; o cliente acrescenta /v1/messages
    KIRO_GATEWAY_API_KEY: str | None = None

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:8000",
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Memória por Conversation (ADR 0003)
    MEMORY_WINDOW: int = 20  # Messages na Recent Window
    SUMMARY_EVERY: int = 20  # Messages fora da janela e não resumidas que disparam um novo Summary
    HISTORY_SEARCH_LIMIT: int = 8  # resultados da History Search

    # Realtime
    REALTIME_REDIS_CHANNEL: str = "neuralilux:realtime:events"
    TOOL_EVENT_PREVIEW_LIMIT: int = 240
    TOOL_EVENT_INCLUDE_RAW_PAYLOADS: bool = False

    @model_validator(mode="after")
    def _refuse_example_secret_key(self) -> "Settings":
        if self.ENVIRONMENT != "development" and self.SECRET_KEY.startswith(_INSECURE_SECRET_KEY_PREFIX):
            raise ValueError(
                "SECRET_KEY de exemplo nao pode ser usada com ENVIRONMENT != development; defina uma chave forte"
            )
        return self

    @model_validator(mode="after")
    def _refuse_example_webhook_token(self) -> "Settings":
        token = self.EVOLUTION_WEBHOOK_TOKEN
        if self.ENVIRONMENT != "development" and (not token or token.startswith(_INSECURE_WEBHOOK_TOKEN_PREFIX)):
            raise ValueError(
                "EVOLUTION_WEBHOOK_TOKEN vazio ou de exemplo nao pode ser usado com ENVIRONMENT != development; "
                "defina um token forte (sem ele o webhook da Evolution responde 401)"
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
