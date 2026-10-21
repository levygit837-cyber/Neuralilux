from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


_INSECURE_SECRET_KEY_PREFIX = "change-me-in-production"


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Neuralilux"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+psycopg://neuralilux:neuralilux_password@localhost:5434/neuralilux"

    # Redis
    REDIS_URL: str = "redis://:redis_password@localhost:6380/0"

    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8081"
    EVOLUTION_API_KEY: str = "3v0lut10n_4P1_K3y_S3cur3_2026!"
    EVOLUTION_WEBSOCKET_ENABLED: bool = False

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://neuralilux:rabbitmq_password@localhost:5672/neuralilux"

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # Anthropic
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # LM Studio (local inference)
    LM_STUDIO_URL: str = "http://localhost:1234"
    LM_STUDIO_MODEL: str = "nvidia/nemotron-3-nano-4b"
    LM_STUDIO_MAX_TOKENS: int = 2048
    LM_STUDIO_TEMPERATURE: float = 0.7
    LM_STUDIO_DISABLE_THINKING: bool = True

    # Google Gemini
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.1-flash-lite-preview"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.7

    # Vertex AI Express Mode (API Key based, no project ID needed)
    VERTEX_API_KEY: str | None = None
    VERTEX_MODEL: str = "gemini-3.1-flash-lite-preview"
    VERTEX_MAX_TOKENS: int = 2048
    VERTEX_TEMPERATURE: float = 0.7
    VERTEX_TIMEOUT: float = 30.0

    # Gateway local "Kiro-backend" (semeado na primeira execucao; depois editavel pela API/UI)
    KIRO_GATEWAY_URL: str = "http://localhost:5580"  # raiz; o cliente acrescenta /v1/messages
    KIRO_GATEWAY_API_KEY: str | None = None

    # Agent Configuration (Global defaults)
    AGENT_MAX_HISTORY_MESSAGES: int = 10
    AGENT_TEMPERATURE: float = 0.2
    AGENT_ENABLED_BY_DEFAULT: bool = False
    AGENT_RESPONSE_MAX_TOKENS: int = 250
    AGENT_INFERENCE_PROVIDER: str = "vertex"  # "lm_studio", "gemini", or "vertex" (global fallback)

    # WhatsApp Agent Configuration
    WHATSAPP_AGENT_INFERENCE_PROVIDER: str = "vertex"  # "lm_studio", "gemini", or "vertex"
    WHATSAPP_AGENT_GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    WHATSAPP_AGENT_GEMINI_MAX_TOKENS: int = 2048
    WHATSAPP_AGENT_GEMINI_TEMPERATURE: float = 0.7
    WHATSAPP_AGENT_LM_STUDIO_MODEL: str = "qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2"
    WHATSAPP_AGENT_LM_STUDIO_MAX_TOKENS: int = 2048
    WHATSAPP_AGENT_LM_STUDIO_TEMPERATURE: float = 0.7

    # WhatsApp Agent Vertex Configuration
    WHATSAPP_AGENT_VERTEX_MODEL: str = "gemini-3.1-flash-lite-preview"
    WHATSAPP_AGENT_VERTEX_MAX_TOKENS: int = 2048
    WHATSAPP_AGENT_VERTEX_TEMPERATURE: float = 0.7

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:8000",
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

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

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
