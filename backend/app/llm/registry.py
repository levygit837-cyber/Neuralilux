"""Resolve qual modelo de Gateway atende cada tipo de agente.

Ordem: atribuicao do `agent_type` -> atribuicao `default` -> `LLMNotConfiguredError`.
Resolucoes bem-sucedidas ficam em cache por poucos segundos para nao consultar o banco a
cada chamada; falhas nunca sao cacheadas. Escritas na API chamam `invalidate()`.
"""
import time

import structlog
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.crypto import SecretDecryptionError, decrypt_secret, encrypt_secret, reencrypt_secret
from app.llm.client import DEFAULT_TIMEOUT_SECONDS, GatewayMessagesClient
from app.llm.errors import LLMNotConfiguredError
from app.models import GatewayAssignment, GatewayModel, InferenceGateway

logger = structlog.get_logger()

DEFAULT_AGENT_TYPE = "default"
KIRO_GATEWAY_NAME = "Kiro-backend"
KIRO_MODEL_ID = "claude-sonnet-5.5"

_CACHE_TTL_SECONDS = 5.0
Resolved = tuple[GatewayMessagesClient, str, str | None]
_cache: dict[str, tuple[float, Resolved]] = {}


def invalidate() -> None:
    _cache.clear()


def build_client(
    gateway: InferenceGateway, *, timeout: float | None = None, max_attempts: int | None = None
) -> GatewayMessagesClient:
    """Cliente para um Gateway cadastrado. `LLMNotConfiguredError` se a chave nao abre.

    `timeout` e `max_attempts` sobrescrevem o timeout salvo e o retry padrao (usado por probe e listagem).
    """
    try:
        api_key = decrypt_secret(gateway.api_key_encrypted) if gateway.api_key_encrypted else None
    except SecretDecryptionError as exc:
        raise LLMNotConfiguredError(f"Gateway '{gateway.name}': {exc}") from exc
    options: dict = {}
    if max_attempts is not None:
        options["max_attempts"] = max_attempts
    return GatewayMessagesClient(
        base_url=gateway.base_url,
        api_key=api_key,
        timeout=timeout if timeout is not None else float(gateway.timeout_seconds or DEFAULT_TIMEOUT_SECONDS),
        gateway_name=gateway.name,
        **options,
    )


def _lookup(db: Session, agent_type: str) -> GatewayModel:
    for key in dict.fromkeys((agent_type, DEFAULT_AGENT_TYPE)):
        assignment = (
            db.query(GatewayAssignment)
            .options(joinedload(GatewayAssignment.gateway_model).joinedload(GatewayModel.gateway))
            .filter(GatewayAssignment.agent_type == key)
            .first()
        )
        if assignment is None:
            continue
        model = assignment.gateway_model
        if model and model.is_active and model.gateway and model.gateway.is_active:
            return model
        # Atribuicao especifica inativa nao cai silenciosamente no `default`.
        raise LLMNotConfiguredError(f"Modelo atribuido a '{key}' esta inativo")
    raise LLMNotConfiguredError(f"Nenhum Gateway atribuido a '{agent_type}' e sem atribuicao 'default'")


def resolve(agent_type: str) -> Resolved:
    """`(client, model_id, effort)` do modelo atribuido a `agent_type`."""
    cached = _cache.get(agent_type)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    from app.core import database  # import tardio: SessionLocal pode ser trocado em testes

    db = database.SessionLocal()
    try:
        model = _lookup(db, agent_type)
        resolved: Resolved = (build_client(model.gateway), model.model_id, model.reasoning_effort)
    finally:
        db.close()

    _cache[agent_type] = (now, resolved)
    return resolved


def ensure_default_gateway(db: Session) -> InferenceGateway | None:
    """Cadastra o container `kiro-backend` (Sonnet 5.5, effort low) como Gateway padrao.

    Idempotente: se ja existe um Gateway com esse nome, nao altera nada (preserva edicoes do usuario).
    """
    if db.query(InferenceGateway).filter(InferenceGateway.name == KIRO_GATEWAY_NAME).first():
        return None

    gateway = InferenceGateway(
        name=KIRO_GATEWAY_NAME,
        base_url=settings.KIRO_GATEWAY_URL,
        api_key_encrypted=encrypt_secret(settings.KIRO_GATEWAY_API_KEY) if settings.KIRO_GATEWAY_API_KEY else None,
        timeout_seconds=int(DEFAULT_TIMEOUT_SECONDS),
    )
    gateway.models.append(
        GatewayModel(name="Sonnet 5.5 (low)", model_id=KIRO_MODEL_ID, reasoning_effort="low")
    )
    db.add(gateway)
    db.flush()
    if db.get(GatewayAssignment, DEFAULT_AGENT_TYPE) is None:
        db.add(GatewayAssignment(agent_type=DEFAULT_AGENT_TYPE, gateway_model_id=gateway.models[0].id))
    db.commit()
    invalidate()
    return gateway


def reencrypt_gateway_secrets(db: Session) -> int:
    """Converte chaves de API gravadas com derivacao da `SECRET_KEY` para a `GATEWAY_ENCRYPTION_KEY`.

    Aceita os formatos antigos (HKDF e SHA-256 sobre a `SECRET_KEY`). Idempotente. Tokens que nao abrem
    com nenhuma das chaves ficam intactos (o usuario precisa informar a chave de novo). Devolve quantas
    chaves foram convertidas.
    """
    converted = 0
    for gateway in db.query(InferenceGateway).filter(InferenceGateway.api_key_encrypted.isnot(None)).all():
        try:
            token = reencrypt_secret(gateway.api_key_encrypted)
        except SecretDecryptionError:
            logger.warning("Gateway API key cannot be decrypted; left untouched", gateway=gateway.name)
            continue
        if token is not None:
            gateway.api_key_encrypted = token
            converted += 1
    if converted:
        db.commit()
        invalidate()
    return converted
