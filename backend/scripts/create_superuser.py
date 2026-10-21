#!/usr/bin/env python3
"""Cria ou promove um superusuario (necessario para editar Gateways: ADR 0002).

Uso:
    SUPERUSER_EMAIL=admin@empresa.com SUPERUSER_PASSWORD='...' python scripts/create_superuser.py
    python scripts/create_superuser.py --email admin@empresa.com --password '...'

Idempotente: usuario existente e promovido (senha informada e ignorada, a atual e mantida);
inexistente e criado com a senha informada (hash bcrypt, o mesmo de `app.core.security`).
Prefira as variaveis de ambiente: argumentos de linha de comando aparecem em `ps`.
A senha nunca e impressa.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.models import User

MIN_PASSWORD_LENGTH = 6  # mesmo minimo de `UserCreate`


def ensure_superuser(db: Session, email: str, password: str | None) -> tuple[User, str]:
    """Devolve `(user, action)` com action em `created` | `promoted` | `unchanged`."""
    email = (email or "").strip()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("e-mail invalido")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        if not password or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"senha obrigatoria (minimo {MIN_PASSWORD_LENGTH} caracteres) para criar o usuario")
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Superusuario",
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, "created"

    if user.is_superuser and user.is_active:
        return user, "unchanged"
    user.is_superuser = True
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user, "promoted"


def _open_session() -> Session:
    from app.core.database import SessionLocal

    return SessionLocal()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria ou promove um superusuario.")
    parser.add_argument("--email", default=os.environ.get("SUPERUSER_EMAIL"), help="padrao: $SUPERUSER_EMAIL")
    parser.add_argument("--password", default=os.environ.get("SUPERUSER_PASSWORD"), help="padrao: $SUPERUSER_PASSWORD")
    args = parser.parse_args(argv)

    if not args.email:
        print("Informe o e-mail com --email ou SUPERUSER_EMAIL.", file=sys.stderr)
        return 2

    db = _open_session()
    try:
        user, action = ensure_superuser(db, args.email, args.password)
    except ValueError as exc:
        db.rollback()
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()

    labels = {"created": "criado", "promoted": "promovido a superusuario", "unchanged": "ja era superusuario"}
    print(f"Usuario {user.email}: {labels[action]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
