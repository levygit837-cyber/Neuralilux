#!/usr/bin/env python3
"""Re-criptografa as chaves de API dos Gateways da derivacao da SECRET_KEY para a GATEWAY_ENCRYPTION_KEY.

Cobre tokens HKDF(SECRET_KEY) e SHA-256(SECRET_KEY). Idempotente: rodar de novo nao altera nada.
Chaves que nao abrem com nenhuma das duas ficam intactas e precisam ser informadas de novo pela API.
Passo unico de upgrade: rode antes de subir a app, com a GATEWAY_ENCRYPTION_KEY real e a SECRET_KEY antiga no .env.

Recusa rodar (exit 1, sem tocar no banco) quando a GATEWAY_ENCRYPTION_KEY esta vazia ou e a de exemplo,
mesmo em development: regravar os tokens com uma chave publica nao tem volta.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import EXAMPLE_SECRET_PREFIX, settings
from app.core.database import SessionLocal
from app.llm.registry import reencrypt_gateway_secrets


def main() -> int:
    key = settings.GATEWAY_ENCRYPTION_KEY
    if not key or key.startswith(EXAMPLE_SECRET_PREFIX):
        print(
            "Recusado: GATEWAY_ENCRYPTION_KEY esta vazia ou e a de exemplo. Defina uma chave real no backend/.env "
            '(python3 -c "import secrets; print(secrets.token_urlsafe(48))"), mantenha a SECRET_KEY atual e rode de novo. '
            "Nenhuma chave de Gateway foi alterada.",
            file=sys.stderr,
        )
        return 1
    db = SessionLocal()
    try:
        print(f"Chaves de gateway re-criptografadas: {reencrypt_gateway_secrets(db)}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
