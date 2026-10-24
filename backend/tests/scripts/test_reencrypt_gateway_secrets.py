"""scripts/reencrypt_gateway_secrets.py: migra da SECRET_KEY para a GATEWAY_ENCRYPTION_KEY e nunca usa a chave de exemplo."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.crypto import _fernet_for, decrypt_secret
from app.models import InferenceGateway

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
REAL_KEY = "g" * 48


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_script", _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(db, monkeypatch):
    module = _load("reencrypt_gateway_secrets")
    monkeypatch.setattr(module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    return module


def _old_gateway(db) -> InferenceGateway:
    token = _fernet_for(settings.SECRET_KEY).encrypt(b"sk-old").decode()
    gateway = InferenceGateway(name="old", base_url="http://old.test", api_key_encrypted=token)
    db.add(gateway)
    db.commit()
    return gateway


@pytest.mark.parametrize("example_key", ["change-me-dev-only-gateway-encryption-key", ""])
def test_script_refuses_the_example_key_and_leaves_every_token_untouched(db, script, monkeypatch, capsys, example_key):
    gateway = _old_gateway(db)
    before = gateway.api_key_encrypted
    monkeypatch.setattr(settings, "GATEWAY_ENCRYPTION_KEY", example_key)

    assert script.main() == 1

    assert "GATEWAY_ENCRYPTION_KEY" in capsys.readouterr().err
    db.expire_all()
    assert db.get(InferenceGateway, gateway.id).api_key_encrypted == before


def test_script_with_a_real_key_migrates_and_a_second_run_changes_nothing(db, script, monkeypatch, capsys):
    gateway = _old_gateway(db)
    monkeypatch.setattr(settings, "GATEWAY_ENCRYPTION_KEY", REAL_KEY)

    assert script.main() == 0
    assert "re-criptografadas: 1" in capsys.readouterr().out
    db.expire_all()
    migrated = db.get(InferenceGateway, gateway.id).api_key_encrypted
    assert decrypt_secret(migrated) == "sk-old"

    assert script.main() == 0
    assert "re-criptografadas: 0" in capsys.readouterr().out
    db.expire_all()
    assert db.get(InferenceGateway, gateway.id).api_key_encrypted == migrated


def test_seed_leaves_existing_gateway_tokens_alone(db, monkeypatch):
    """O seed roda em dev com a chave de exemplo: nao pode regravar tokens (a migracao e o script, uma vez)."""
    seed = _load("seed_data")
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db.get_bind()))
    gateway = _old_gateway(db)
    before = gateway.api_key_encrypted

    seed.main()

    db.expire_all()
    assert db.get(InferenceGateway, gateway.id).api_key_encrypted == before
