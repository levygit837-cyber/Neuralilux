"""Criptografia simetrica de segredos em repouso (chaves de API de gateways).

A chave Fernet e derivada de `settings.SECRET_KEY` (SHA-256 -> base64 urlsafe).
Trocar `SECRET_KEY` invalida os segredos ja gravados: o usuario precisa
informar as chaves de API novamente.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretDecryptionError(Exception):
    """O segredo nao pode ser descriptografado com a SECRET_KEY atual."""


@lru_cache(maxsize=4)
def _fernet_for(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet_for(settings.SECRET_KEY).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet_for(settings.SECRET_KEY).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Nao foi possivel descriptografar o segredo; a SECRET_KEY mudou desde que foi salvo."
        ) from exc
