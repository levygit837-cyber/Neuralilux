"""Recusa subir com segredos de exemplo/vazios sem ENVIRONMENT=development explícito."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings

DEFAULT_KEY = "change-me-in-production-use-strong-secret-key-here"
STRONG = {"SECRET_KEY": "s" * 48, "EVOLUTION_WEBHOOK_TOKEN": "w" * 32, "GATEWAY_ENCRYPTION_KEY": "g" * 48}


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def _without_environment(monkeypatch) -> None:
    # A suíte força ENVIRONMENT=development (conftest); aqui simulamos o ambiente sem a variável.
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def test_without_environment_the_example_secrets_are_refused_and_the_message_says_what_to_set(monkeypatch):
    _without_environment(monkeypatch)
    with pytest.raises(ValidationError) as info:
        _settings()
    message = str(info.value)
    for name in ("SECRET_KEY", "EVOLUTION_WEBHOOK_TOKEN", "GATEWAY_ENCRYPTION_KEY", "ENVIRONMENT=development"):
        assert name in message


def test_without_environment_and_strong_secrets_the_app_boots_as_production(monkeypatch):
    _without_environment(monkeypatch)
    assert _settings(**STRONG).ENVIRONMENT == "production"


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("name", ["SECRET_KEY", "EVOLUTION_WEBHOOK_TOKEN", "GATEWAY_ENCRYPTION_KEY"])
@pytest.mark.parametrize("bad", ["", "change-me", "change-me-in-production-use-strong-secret-key-minimum-32-characters"])
def test_empty_or_example_secret_is_refused_outside_development(environment, name, bad):
    with pytest.raises(ValidationError, match=name):
        _settings(ENVIRONMENT=environment, **{**STRONG, name: bad})


def test_gateway_encryption_key_must_differ_from_secret_key():
    with pytest.raises(ValidationError, match="GATEWAY_ENCRYPTION_KEY igual"):
        _settings(ENVIRONMENT="production", **{**STRONG, "GATEWAY_ENCRYPTION_KEY": STRONG["SECRET_KEY"]})


def test_real_secrets_are_accepted_in_production():
    assert _settings(ENVIRONMENT="production", **STRONG).ENVIRONMENT == "production"


def test_example_secrets_and_empty_webhook_token_are_allowed_in_explicit_development():
    settings = _settings(ENVIRONMENT="development", SECRET_KEY=DEFAULT_KEY, EVOLUTION_WEBHOOK_TOKEN="")
    assert settings.SECRET_KEY == DEFAULT_KEY and settings.EVOLUTION_WEBHOOK_TOKEN == ""
