"""Registry de Gateways: resolucao por agent_type, cache, falhas explicitas, seed e re-criptografia."""
import base64
import hashlib

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.llm import registry
from app.llm.client import GatewayMessagesClient
from app.llm.errors import LLMNotConfiguredError
from app.models import GatewayAssignment, GatewayModel, InferenceGateway


def _seed(db, *, agent_type="default", model_active=True, name="gw", api_key="k", effort="low") -> GatewayModel:
    gateway = InferenceGateway(
        name=name,
        base_url="http://gw.test",
        api_key_encrypted=encrypt_secret(api_key) if api_key else None,
        timeout_seconds=45,
    )
    model = GatewayModel(name="m", model_id="m1", reasoning_effort=effort, is_active=model_active)
    gateway.models.append(model)
    db.add(gateway)
    db.flush()
    db.add(GatewayAssignment(agent_type=agent_type, gateway_model_id=model.id))
    db.commit()
    registry.invalidate()
    return model


def test_resolve_returns_client_model_and_effort(db):
    _seed(db)
    client, model, effort = registry.resolve("whatsapp_agent")

    assert isinstance(client, GatewayMessagesClient)
    assert (model, effort) == ("m1", "low")


def test_resolve_prefers_specific_assignment_then_default(db):
    _seed(db, agent_type="default", name="gw-default")
    specific = GatewayModel(name="s", model_id="specific", gateway_id=db.query(InferenceGateway).one().id)
    db.add(specific)
    db.flush()
    db.add(GatewayAssignment(agent_type="whatsapp_agent", gateway_model_id=specific.id))
    db.commit()
    registry.invalidate()

    assert registry.resolve("whatsapp_agent")[1] == "specific"
    assert registry.resolve("outro_tipo")[1] == "m1"  # sem atribuicao propria, cai no default


def test_resolve_without_any_assignment_raises_not_configured(db):
    with pytest.raises(LLMNotConfiguredError):
        registry.resolve("default")


def test_resolve_inactive_model_raises_not_configured(db):
    _seed(db, model_active=False)
    with pytest.raises(LLMNotConfiguredError):
        registry.resolve("default")


def test_inactive_specific_assignment_does_not_fall_back_to_default(db):
    _seed(db, agent_type="default", name="gw-default")
    inactive = GatewayModel(name="off", model_id="off", is_active=False, gateway_id=db.query(InferenceGateway).one().id)
    db.add(inactive)
    db.flush()
    db.add(GatewayAssignment(agent_type="whatsapp_agent", gateway_model_id=inactive.id))
    db.commit()
    registry.invalidate()

    with pytest.raises(LLMNotConfiguredError):
        registry.resolve("whatsapp_agent")


def test_undecryptable_api_key_raises_explicitly_and_is_not_cached(db):
    model = _seed(db)
    gateway = db.get(InferenceGateway, model.gateway_id)
    good_token = gateway.api_key_encrypted
    gateway.api_key_encrypted = "gAAAAA-token-corrompido"
    db.commit()
    registry.invalidate()

    with pytest.raises(LLMNotConfiguredError, match="SECRET_KEY"):
        registry.resolve("default")
    # Segunda chamada nao devolve um `None` em cache: continua falhando ate corrigir a chave...
    with pytest.raises(LLMNotConfiguredError):
        registry.resolve("default")

    # ...e, corrigida a chave, a proxima resolucao funciona sem esperar o TTL expirar.
    gateway.api_key_encrypted = good_token
    db.commit()
    assert registry.resolve("default")[1] == "m1"


def test_resolution_is_cached_until_invalidated(db):
    model = _seed(db)
    first = registry.resolve("default")
    db.get(GatewayModel, model.id).model_id = "changed"
    db.commit()

    assert registry.resolve("default")[1] == "m1"  # cache de 5 s
    registry.invalidate()
    assert registry.resolve("default")[1] == "changed"
    assert first[1] == "m1"


def test_ensure_default_gateway_seeds_kiro_backend_with_messages_model_and_is_idempotent(db):
    first = registry.ensure_default_gateway(db)
    assert first is not None and first.name == "Kiro-backend"
    assert not first.base_url.rstrip("/").endswith("/v1/messages")
    model = first.models[0]
    assert (model.model_id, model.reasoning_effort) == ("claude-sonnet-5.5", "low")
    assert db.get(GatewayAssignment, "default").gateway_model_id == model.id

    model.reasoning_effort = "high"
    db.commit()
    assert registry.ensure_default_gateway(db) is None
    assert db.query(GatewayModel).one().reasoning_effort == "high"  # preserva edicao do usuario


def _legacy_token(plaintext: str) -> str:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key).encrypt(plaintext.encode()).decode()


def test_reencrypt_migrates_legacy_sha256_tokens_and_is_idempotent(db):
    legacy = InferenceGateway(name="old", base_url="http://old.test", api_key_encrypted=_legacy_token("sk-old"))
    current = InferenceGateway(name="new", base_url="http://new.test", api_key_encrypted=encrypt_secret("sk-new"))
    no_key = InferenceGateway(name="open", base_url="http://open.test")
    db.add_all([legacy, current, no_key])
    db.commit()

    assert registry.reencrypt_gateway_secrets(db) == 1
    db.expire_all()
    assert decrypt_secret(db.get(InferenceGateway, legacy.id).api_key_encrypted) == "sk-old"
    assert decrypt_secret(db.get(InferenceGateway, current.id).api_key_encrypted) == "sk-new"

    assert registry.reencrypt_gateway_secrets(db) == 0


def test_reencrypt_skips_tokens_that_open_with_neither_key(db):
    db.add(InferenceGateway(name="broken", base_url="http://b.test", api_key_encrypted="lixo"))
    db.commit()

    assert registry.reencrypt_gateway_secrets(db) == 0


def test_resolve_builds_client_with_the_gateway_timeout_and_default_retry(db, monkeypatch):
    _seed(db)  # timeout_seconds=45
    seen = {}
    real = registry.GatewayMessagesClient

    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(registry, "GatewayMessagesClient", spy)
    registry.resolve("default")

    assert seen["timeout"] == 45.0 and "max_attempts" not in seen
