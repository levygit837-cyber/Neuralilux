#!/usr/bin/env python3
"""Re-criptografa as chaves de API dos Gateways da derivacao da SECRET_KEY para a GATEWAY_ENCRYPTION_KEY.

Cobre tokens HKDF(SECRET_KEY) e SHA-256(SECRET_KEY). Idempotente: rodar de novo nao altera nada.
Chaves que nao abrem com nenhuma das duas ficam intactas e precisam ser informadas de novo pela API.
Passo unico de upgrade: rode antes de subir a app, com GATEWAY_ENCRYPTION_KEY e a SECRET_KEY antiga no .env.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import SessionLocal
from app.llm.registry import reencrypt_gateway_secrets


def main() -> None:
    db = SessionLocal()
    try:
        print(f"Chaves de gateway re-criptografadas: {reencrypt_gateway_secrets(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
