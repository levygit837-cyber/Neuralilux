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


@pytest.mark.parametrize("name", ["SECRET_KEY", "GATEWAY_ENCRYPTION_KEY"])
def test_keys_shorter_than_32_characters_are_refused_outside_development(name):
    with pytest.raises(ValidationError, match=f"{name} com menos de 32"):
        _settings(ENVIRONMENT="production", **{**STRONG, name: "k" * 31})
    assert _settings(ENVIRONMENT="production", **{**STRONG, name: "k" * 32}).ENVIRONMENT == "production"


def test_gateway_encryption_key_must_differ_from_secret_key():
    with pytest.raises(ValidationError, match="GATEWAY_ENCRYPTION_KEY igual"):
        _settings(ENVIRONMENT="production", **{**STRONG, "GATEWAY_ENCRYPTION_KEY": STRONG["SECRET_KEY"]})


def test_real_secrets_are_accepted_in_production():
    assert _settings(ENVIRONMENT="production", **STRONG).ENVIRONMENT == "production"


def test_example_secrets_and_empty_webhook_token_are_allowed_in_explicit_development():
    settings = _settings(ENVIRONMENT="development", SECRET_KEY=DEFAULT_KEY, EVOLUTION_WEBHOOK_TOKEN="")
    assert settings.SECRET_KEY == DEFAULT_KEY and settings.EVOLUTION_WEBHOOK_TOKEN == ""


def test_debounce_max_wait_shorter_than_the_window_is_refused():
    with pytest.raises(ValidationError, match="DEBOUNCE_MAX_WAIT_SECONDS"):
        _settings(ENVIRONMENT="development", DEBOUNCE_SECONDS=3, DEBOUNCE_MAX_WAIT_SECONDS=1)


@pytest.mark.parametrize("name", ["TURN_TIMEOUT_SECONDS", "TOOL_TIMEOUT_SECONDS"])
def test_non_positive_deadlines_are_refused(name):
    with pytest.raises(ValidationError, match="maiores que zero"):
        _settings(ENVIRONMENT="development", **{name: 0})


def test_tool_timeout_longer_than_the_turn_timeout_is_refused():
    with pytest.raises(ValidationError, match="TOOL_TIMEOUT_SECONDS deve ser menor ou igual"):
        _settings(ENVIRONMENT="development", TURN_TIMEOUT_SECONDS=10, TOOL_TIMEOUT_SECONDS=20)


def test_tool_timeout_equal_to_the_turn_timeout_is_accepted():
    assert _settings(ENVIRONMENT="development", TURN_TIMEOUT_SECONDS=10, TOOL_TIMEOUT_SECONDS=10).TOOL_TIMEOUT_SECONDS == 10


def test_claim_lease_not_longer_than_the_debounce_cap_plus_turn_timeout_is_refused():
    with pytest.raises(ValidationError, match="TURN_CLAIM_LEASE_SECONDS deve ser maior"):
        _settings(
            ENVIRONMENT="development", DEBOUNCE_MAX_WAIT_SECONDS=15, TURN_TIMEOUT_SECONDS=90, TURN_CLAIM_LEASE_SECONDS=105
        )


def test_claim_lease_longer_than_the_debounce_cap_plus_turn_timeout_is_accepted():
    settings = _settings(
        ENVIRONMENT="development", DEBOUNCE_MAX_WAIT_SECONDS=15, TURN_TIMEOUT_SECONDS=90, TURN_CLAIM_LEASE_SECONDS=106
    )
    assert settings.TURN_CLAIM_LEASE_SECONDS == 106
