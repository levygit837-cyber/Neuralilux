from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Neuralilux"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://neuralilux:neuralilux_password@localhost:5432/neuralilux"

    # Redis
    REDIS_URL: str = "redis://:redis_password@localhost:6379/0"

    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8081"
    EVOLUTION_API_KEY: str = "3v0lut10n_4P1_K3y_S3cur3_2026!"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

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
    LM_STUDIO_MODEL: str = "local-model"
    LM_STUDIO_MAX_TOKENS: int = 2048
    LM_STUDIO_TEMPERATURE: float = 0.7

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
