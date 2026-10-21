"""scripts/create_superuser.py: promover um usuario existente ou criar um, de forma idempotente."""
import importlib.util
from pathlib import Path

import pytest

from app.core.security import verify_password
from app.models.models import User

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_superuser.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("create_superuser_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_creates_a_superuser_with_a_bcrypt_hash(db, script):
    user, action = script.ensure_superuser(db, "admin@example.com", "s3nha-forte")

    assert action == "created"
    stored = db.query(User).filter(User.email == "admin@example.com").one()
    assert stored.id == user.id and stored.is_superuser is True and stored.is_active is True
    assert stored.hashed_password != "s3nha-forte" and verify_password("s3nha-forte", stored.hashed_password)


def test_promotes_an_existing_user_without_touching_the_password(db, script):
    db.add(User(email="dev@example.com", hashed_password="hash-original", full_name="Dev", is_superuser=False))
    db.commit()

    user, action = script.ensure_superuser(db, "dev@example.com", "outra-senha")

    assert action == "promoted"
    db.expire_all()
    stored = db.query(User).filter(User.email == "dev@example.com").one()
    assert stored.is_superuser is True
    assert stored.hashed_password == "hash-original" and stored.full_name == "Dev"


def test_promoting_works_without_a_password(db, script):
    db.add(User(email="dev@example.com", hashed_password="hash-original", is_superuser=False))
    db.commit()

    assert script.ensure_superuser(db, "dev@example.com", None)[1] == "promoted"


def test_reactivates_an_inactive_user_when_promoting(db, script):
    db.add(User(email="dev@example.com", hashed_password="h", is_active=False, is_superuser=False))
    db.commit()

    script.ensure_superuser(db, "dev@example.com", None)

    db.expire_all()
    assert db.query(User).one().is_active is True


def test_is_idempotent(db, script):
    script.ensure_superuser(db, "admin@example.com", "s3nha-forte")
    hash_before = db.query(User).one().hashed_password

    _, action = script.ensure_superuser(db, "admin@example.com", "s3nha-forte")

    assert action == "unchanged"
    db.expire_all()
    assert db.query(User).count() == 1 and db.query(User).one().hashed_password == hash_before


def test_creating_requires_a_valid_password_and_email(db, script):
    with pytest.raises(ValueError, match="senha"):
        script.ensure_superuser(db, "novo@example.com", None)
    with pytest.raises(ValueError, match="senha"):
        script.ensure_superuser(db, "novo@example.com", "123")
    with pytest.raises(ValueError, match="e-mail"):
        script.ensure_superuser(db, "sem-arroba", "s3nha-forte")
    assert db.query(User).count() == 0


def test_cli_reads_email_and_password_from_env_and_never_prints_the_password(db, script, monkeypatch, capsys):
    monkeypatch.setenv("SUPERUSER_EMAIL", "env@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "senha-so-no-env")
    monkeypatch.setattr(script, "_open_session", lambda: db)

    assert script.main([]) == 0

    out = capsys.readouterr()
    assert "senha-so-no-env" not in out.out + out.err
    assert "env@example.com" in out.out
    assert db.query(User).filter(User.email == "env@example.com").one().is_superuser is True


def test_cli_args_override_env_and_missing_email_fails_without_leaking(db, script, monkeypatch, capsys):
    monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)
    monkeypatch.setattr(script, "_open_session", lambda: db)

    assert script.main(["--password", "segredo-do-arg"]) == 2
    assert script.main(["--email", "arg@example.com", "--password", "segredo-do-arg"]) == 0

    out = capsys.readouterr()
    assert "segredo-do-arg" not in out.out + out.err
    assert db.query(User).filter(User.email == "arg@example.com").one().is_superuser is True


def test_seed_keeps_dev_user_non_superuser_unless_opted_in(db, monkeypatch):
    spec = importlib.util.spec_from_file_location("seed_data_script", _SCRIPT.with_name("seed_data.py"))
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)

    monkeypatch.delenv("SEED_DEV_SUPERUSER", raising=False)
    assert seed.create_or_update_test_user(db, "company-1").is_superuser is False

    monkeypatch.setenv("SEED_DEV_SUPERUSER", "1")
    assert seed.create_or_update_test_user(db, "company-1").is_superuser is True

    monkeypatch.setenv("SEED_DEV_SUPERUSER", "0")
    assert seed.create_or_update_test_user(db, "company-1").is_superuser is False
