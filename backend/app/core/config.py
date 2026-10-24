import ipaddress
from typing import List

from pydantic import PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


EXAMPLE_SECRET_PREFIX = "change-me"  # todo valor de exemplo do repo (.env.example e defaults) começa assim
_DEVELOPMENT = "development"
_MIN_KEY_LENGTH = 32
_GENERATE_HINT = 'python3 -c "import secrets; print(secrets.token_urlsafe(48))"'


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Neuralilux"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "production"  # padrão seguro: só "development" explícito libera os defaults de exemplo e o /docs
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
    HANDOFF_SWEEP_INTERVAL_SECONDS: int = 60  # de quanto em quanto tempo o worker expira Handoffs sem Attendant

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-strong-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Cookie de login do navegador (ADR 0008). Vazio = cookie só do host da API; defina o domínio pai
    # (ex.: ".exemplo.com") só se o frontend e a API ficarem em subdomínios diferentes do mesmo site.
    AUTH_COOKIE_DOMAIN: str | None = None

    # Superfície pública (#85). Cadastro anônimo desligado por padrão: usuários saem do `create_superuser.py` ou de
    # um superusuário autenticado. Limites por IP em /auth/login e /auth/register (janela fixa no Redis; o que
    # acontece com o Redis fora está em docs/operations.md).
    ALLOW_PUBLIC_REGISTRATION: bool = False
    LOGIN_RATE_LIMIT_ATTEMPTS: PositiveInt = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: PositiveInt = 60
    REGISTER_RATE_LIMIT_ATTEMPTS: PositiveInt = 5
    REGISTER_RATE_LIMIT_WINDOW_SECONDS: PositiveInt = 3600
    # IPs/CIDRs dos proxies reversos que a app aceita como confiáveis. Só peers desta lista têm o cabeçalho
    # X-Forwarded-For lido; vazio (padrão) = o IP do cliente é sempre o do peer TCP.
    TRUSTED_PROXIES: List[str] = []

    # Criptografia em repouso das chaves de API dos Gateways. Independente da SECRET_KEY: rotacionar o JWT não
    # destrói as chaves salvas. Trocar esta invalida as chaves gravadas (é preciso informá-las de novo).
    GATEWAY_ENCRYPTION_KEY: str = "change-me-dev-only-gateway-encryption-key"

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

    # Memória por Conversation (ADR 0003)
    MEMORY_WINDOW: int = 20  # máximo de Messages na Recent Window
    MEMORY_WINDOW_BLOCK: int = 10  # a janela descarta as mais antigas em blocos deste tamanho (1 a MEMORY_WINDOW)
    SUMMARY_EVERY: int = 20  # Messages de Sessions anteriores, não resumidas, que disparam um novo Summary
    HISTORY_SEARCH_LIMIT: int = 8  # resultados da History Search

    # Agrupamento de Messages picadas (ticket #36)
    DEBOUNCE_SECONDS: float = 3.0  # pausa do Contact antes do Turn; 0 desliga o agrupamento
    TYPING_REFRESH_SECONDS: float = 20.0  # a presença "digitando" expira sozinha; renovada enquanto o Turn roda
    DEBOUNCE_MAX_WAIT_SECONDS: float = 15.0  # teto da espera da rajada: passado isso o Turn roda com o que já chegou

    # Prazos do Turn (issue #89)
    TURN_TIMEOUT_SECONDS: float = 90.0  # o Turn inteiro; vencido, cancela Gateway e Tools e o Contact recebe o fallback
    TOOL_TIMEOUT_SECONDS: float = 15.0  # cada Tool; vencida, vira tool_result com is_error e rollback
    TURN_RETRY_BUDGET: int = 2  # retries ao Gateway que o Turn inteiro pode gastar (não por chamada)
    TURN_RETRY_WAIT_SECONDS: float = 20.0  # espera total (backoff com jitter ou Retry-After) que os retries do Turn podem gastar

    # Realtime
    REALTIME_REDIS_CHANNEL: str = "neuralilux:realtime:events"
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = 2.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 2.0
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = 30
    REALTIME_PUBLISH_TIMEOUT_SECONDS: float = 1.0  # teto que um evento de UI pode segurar o Turn
    REALTIME_PUBLISH_COOLDOWN_SECONDS: float = 5.0  # após falhar, os eventos seguintes são descartados sem tentar
    TOOL_EVENT_PREVIEW_LIMIT: int = 240
    TOOL_EVENT_INCLUDE_RAW_PAYLOADS: bool = False

    @model_validator(mode="after")
    def _refuse_example_secrets_outside_development(self) -> "Settings":
        if self.ENVIRONMENT == _DEVELOPMENT:
            return self
        problems = [
            f"{name} vazio ou de exemplo"
            for name, value in (
                ("SECRET_KEY", self.SECRET_KEY),
                ("EVOLUTION_WEBHOOK_TOKEN", self.EVOLUTION_WEBHOOK_TOKEN),
                ("GATEWAY_ENCRYPTION_KEY", self.GATEWAY_ENCRYPTION_KEY),
            )
            if not value or value.startswith(EXAMPLE_SECRET_PREFIX)
        ]
        problems += [
            f"{name} com menos de {_MIN_KEY_LENGTH} caracteres"
            for name, value in (("SECRET_KEY", self.SECRET_KEY), ("GATEWAY_ENCRYPTION_KEY", self.GATEWAY_ENCRYPTION_KEY))
            if value and not value.startswith(EXAMPLE_SECRET_PREFIX) and len(value) < _MIN_KEY_LENGTH
        ]
        if self.SECRET_KEY and self.SECRET_KEY == self.GATEWAY_ENCRYPTION_KEY:
            problems.append("GATEWAY_ENCRYPTION_KEY igual à SECRET_KEY (devem ser valores diferentes)")
        if problems:
            raise ValueError(
                f"Configuração recusada com ENVIRONMENT='{self.ENVIRONMENT}' (sem ENVIRONMENT definido vale 'production'): "
                + "; ".join(problems)
                + ". Em desenvolvimento local, defina ENVIRONMENT=development no backend/.env. "
                f"Fora dele, defina valores fortes e distintos para SECRET_KEY, EVOLUTION_WEBHOOK_TOKEN e "
                f"GATEWAY_ENCRYPTION_KEY, as duas chaves com ao menos {_MIN_KEY_LENGTH} caracteres (gere cada um com: {_GENERATE_HINT})"
            )
        return self

    @model_validator(mode="after")
    def _trusted_proxies_are_networks(self) -> "Settings":
        for entry in self.TRUSTED_PROXIES:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                raise ValueError(f"TRUSTED_PROXIES: '{entry}' não é um IP nem um CIDR válido")
        return self

    @model_validator(mode="after")
    def _window_block_fits_the_window(self) -> "Settings":
        if not 1 <= self.MEMORY_WINDOW_BLOCK <= self.MEMORY_WINDOW:
            raise ValueError("MEMORY_WINDOW_BLOCK deve ficar entre 1 e MEMORY_WINDOW")
        return self

    @model_validator(mode="after")
    def _deadlines_are_positive_and_ordered(self) -> "Settings":
        if min(self.TURN_TIMEOUT_SECONDS, self.TOOL_TIMEOUT_SECONDS) <= 0:
            raise ValueError("TURN_TIMEOUT_SECONDS e TOOL_TIMEOUT_SECONDS devem ser maiores que zero")
        if self.TOOL_TIMEOUT_SECONDS > self.TURN_TIMEOUT_SECONDS:
            raise ValueError("TOOL_TIMEOUT_SECONDS deve ser menor ou igual a TURN_TIMEOUT_SECONDS (o prazo da Tool nunca valeria)")
        if self.TURN_RETRY_BUDGET < 0 or self.TURN_RETRY_WAIT_SECONDS < 0:
            raise ValueError("TURN_RETRY_BUDGET e TURN_RETRY_WAIT_SECONDS não podem ser negativos")
        if self.DEBOUNCE_SECONDS > 0 and self.DEBOUNCE_MAX_WAIT_SECONDS < self.DEBOUNCE_SECONDS:
            raise ValueError("DEBOUNCE_MAX_WAIT_SECONDS deve ser maior ou igual a DEBOUNCE_SECONDS")
        return self

    @model_validator(mode="after")
    def _cooldown_outlasts_publish_timeout(self) -> "Settings":
        if self.REALTIME_PUBLISH_COOLDOWN_SECONDS <= self.REALTIME_PUBLISH_TIMEOUT_SECONDS:
            raise ValueError(
                "REALTIME_PUBLISH_COOLDOWN_SECONDS deve ser maior que REALTIME_PUBLISH_TIMEOUT_SECONDS "
                "(senão o cooldown acaba antes de o teto de um publish terminar e cada evento paga o teto de novo)"
            )
        return self

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
