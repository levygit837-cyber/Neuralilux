#!/usr/bin/env python3
"""Re-criptografa as chaves de API dos Gateways da derivacao SHA-256 antiga para HKDF.

Idempotente: rodar de novo nao altera nada. Chaves que nao abrem com a SECRET_KEY atual
ficam intactas e precisam ser informadas de novo pela API.
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
