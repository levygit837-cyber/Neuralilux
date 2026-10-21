"""Recusa subir com a SECRET_KEY ou o EVOLUTION_WEBHOOK_TOKEN de exemplo/vazio fora de desenvolvimento."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings

DEFAULT_KEY = "change-me-in-production-use-strong-secret-key-here"


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_default_secret_key_is_refused_outside_development(environment):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(ENVIRONMENT=environment, SECRET_KEY=DEFAULT_KEY)


def test_example_env_secret_key_is_also_refused_in_production():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(ENVIRONMENT="production", SECRET_KEY="change-me-in-production-use-strong-secret-key-minimum-32-characters")


def test_default_secret_key_is_allowed_in_development():
    assert _settings(ENVIRONMENT="development", SECRET_KEY=DEFAULT_KEY).SECRET_KEY == DEFAULT_KEY


def test_real_secret_key_is_accepted_in_production():
    assert _settings(ENVIRONMENT="production", SECRET_KEY="x" * 48, EVOLUTION_WEBHOOK_TOKEN="w" * 32).ENVIRONMENT == "production"


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("token", ["", "change-me", "change-me-in-production"])
def test_empty_or_example_webhook_token_is_refused_outside_development(environment, token):
    with pytest.raises(ValidationError, match="EVOLUTION_WEBHOOK_TOKEN"):
        _settings(ENVIRONMENT=environment, SECRET_KEY="x" * 48, EVOLUTION_WEBHOOK_TOKEN=token)


def test_empty_webhook_token_is_allowed_in_development():
    assert _settings(ENVIRONMENT="development", EVOLUTION_WEBHOOK_TOKEN="").EVOLUTION_WEBHOOK_TOKEN == ""
