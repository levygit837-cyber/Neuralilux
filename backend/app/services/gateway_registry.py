"""Resolve qual modelo de gateway atende cada tipo de agente.

Ordem de resolucao: atribuicao do `agent_type` -> atribuicao `default` -> None (provedores padrao).
O resultado e cacheado por poucos segundos para nao consultar o banco a cada chamada de inferencia;
escritas na API chamam `invalidate()`.
"""
import time
from typing import Dict, Optional, Tuple

import structlog
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.crypto import SecretDecryptionError, decrypt_secret, encrypt_secret
from app.models.models import GatewayAssignment, GatewayModel, InferenceGateway
from app.services.gateway_inference_service import GatewayInferenceService

logger = structlog.get_logger()

DEFAULT_AGENT_TYPE = "default"
AGENT_TYPES = ("default", "whatsapp_agent", "super_agent")
KIRO_GATEWAY_NAME = "Kiro-backend"

_CACHE_TTL_SECONDS = 5.0
_cache: Dict[str, Tuple[float, Optional[GatewayInferenceService]]] = {}


def invalidate() -> None:
    _cache.clear()


def build_service(gateway_model: GatewayModel) -> GatewayInferenceService:
    gateway = gateway_model.gateway
    api_key = decrypt_secret(gateway.api_key_encrypted) if gateway.api_key_encrypted else None
    return GatewayInferenceService(
        base_url=gateway.base_url,
        model=gateway_model.model_id,
        api_key=api_key,
        reasoning_effort=gateway_model.reasoning_effort,
        max_tokens=gateway_model.max_tokens,
        temperature=gateway_model.temperature,
        timeout=float(gateway.timeout_seconds),
        supports_tools=gateway_model.supports_tools,
        gateway_name=gateway.name,
    )


def _lookup(db: Session, agent_type: str) -> Optional[GatewayModel]:
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
        # Atribuicao especifica inativa nao deve cair silenciosamente no `default`.
        return None
    return None


def get_assigned_service(agent_type: str) -> Optional[GatewayInferenceService]:
    cached = _cache.get(agent_type)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    service: Optional[GatewayInferenceService] = None
    from app.core import database  # import tardio: SessionLocal pode ser trocado em testes

    db = database.SessionLocal()
    try:
        model = _lookup(db, agent_type)
        if model is not None:
            service = build_service(model)
    except SecretDecryptionError as exc:
        logger.error("Gateway API key cannot be decrypted", agent_type=agent_type, error=str(exc))
    except Exception as exc:  # banco indisponivel / tabelas ausentes: usa provedores padrao
        logger.warning("Gateway lookup failed; using default providers", agent_type=agent_type, error=str(exc))
    finally:
        db.close()

    _cache[agent_type] = (now, service)
    return service


def ensure_default_gateway(db: Session) -> Optional[InferenceGateway]:
    """Cadastra o container `kiro-backend` (Sonnet 5.5, effort low) como gateway padrao.

    Idempotente: se ja existe um gateway com esse nome, nao altera nada (preserva edicoes do usuario).
    """
    if db.query(InferenceGateway).filter(InferenceGateway.name == KIRO_GATEWAY_NAME).first():
        return None

    gateway = InferenceGateway(
        name=KIRO_GATEWAY_NAME,
        base_url=settings.KIRO_GATEWAY_URL,
        api_key_encrypted=encrypt_secret(settings.KIRO_GATEWAY_API_KEY) if settings.KIRO_GATEWAY_API_KEY else None,
        timeout_seconds=120,
    )
    gateway.models.append(
        GatewayModel(
            name="Sonnet 5.5 (low)",
            model_id="claude-sonnet-5.5",
            reasoning_effort="low",
        )
    )
    db.add(gateway)
    db.flush()
    if db.get(GatewayAssignment, DEFAULT_AGENT_TYPE) is None:
        db.add(GatewayAssignment(agent_type=DEFAULT_AGENT_TYPE, gateway_model_id=gateway.models[0].id))
    db.commit()
    invalidate()
    return gateway
