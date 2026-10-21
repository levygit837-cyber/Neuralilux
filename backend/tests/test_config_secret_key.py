"""Recusa subir com a SECRET_KEY de exemplo fora de desenvolvimento."""
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
    assert _settings(ENVIRONMENT="production", SECRET_KEY="x" * 48).ENVIRONMENT == "production"
