"""Criptografia simetrica de segredos em repouso (chaves de API de gateways).

A chave Fernet e derivada de `settings.GATEWAY_ENCRYPTION_KEY` com HKDF-SHA256
(`info=b"neuralilux-gateway-secrets"`). Ela e independente da `SECRET_KEY` (JWT): rotacionar o JWT
nao afeta os segredos gravados. Trocar `GATEWAY_ENCRYPTION_KEY` os invalida: o usuario precisa
informar as chaves de API novamente.

Segredos gravados antes da chave propria usavam `SECRET_KEY`, com HKDF ou (ainda antes) com SHA-256
puro. `reencrypt_secret` converte esses tokens; `decrypt_secret` NAO aceita os formatos antigos.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

_HKDF_INFO = b"neuralilux-gateway-secrets"


class SecretDecryptionError(Exception):
    """O segredo nao pode ser descriptografado com a GATEWAY_ENCRYPTION_KEY atual."""


@lru_cache(maxsize=4)
def _fernet_for(key_material: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(key_material.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


@lru_cache(maxsize=4)
def _legacy_fernet_for(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet_for(settings.GATEWAY_ENCRYPTION_KEY).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet_for(settings.GATEWAY_ENCRYPTION_KEY).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Nao foi possivel descriptografar o segredo; a GATEWAY_ENCRYPTION_KEY mudou desde que foi salvo."
        ) from exc


def reencrypt_secret(token: str) -> str | None:
    """Converte um token derivado da `SECRET_KEY` (HKDF ou SHA-256) para a `GATEWAY_ENCRYPTION_KEY`.

    Devolve `None` quando o token ja esta no formato atual (idempotente).
    Levanta `SecretDecryptionError` se nenhum dos formatos abre.
    """
    raw = token.encode("ascii")
    try:
        _fernet_for(settings.GATEWAY_ENCRYPTION_KEY).decrypt(raw)
        return None
    except InvalidToken:
        pass
    for old in (_fernet_for(settings.SECRET_KEY), _legacy_fernet_for(settings.SECRET_KEY)):
        try:
            return encrypt_secret(old.decrypt(raw).decode("utf-8"))
        except InvalidToken:
            continue
    raise SecretDecryptionError(
        "Nao foi possivel descriptografar o segredo; nem a GATEWAY_ENCRYPTION_KEY nem a SECRET_KEY abrem o token."
    )
