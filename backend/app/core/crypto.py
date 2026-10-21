"""Criptografia simetrica de segredos em repouso (chaves de API de gateways).

A chave Fernet e derivada de `settings.SECRET_KEY` com HKDF-SHA256
(`info=b"neuralilux-gateway-secrets"`). Trocar `SECRET_KEY` invalida os segredos ja
gravados: o usuario precisa informar as chaves de API novamente.

Segredos gravados antes do HKDF usavam SHA-256 puro da `SECRET_KEY`. `reencrypt_secret`
converte esses tokens; `decrypt_secret` NAO aceita o formato antigo.
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
    """O segredo nao pode ser descriptografado com a SECRET_KEY atual."""


@lru_cache(maxsize=4)
def _fernet_for(secret_key: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(secret_key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


@lru_cache(maxsize=4)
def _legacy_fernet_for(secret_key: str) -> Fernet:
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


def reencrypt_secret(token: str) -> str | None:
    """Converte um token do formato SHA-256 para HKDF.

    Devolve `None` quando o token ja esta no formato atual (idempotente).
    Levanta `SecretDecryptionError` se nenhum dos dois formatos abre.
    """
    try:
        _fernet_for(settings.SECRET_KEY).decrypt(token.encode("ascii"))
        return None
    except InvalidToken:
        pass
    try:
        plaintext = _legacy_fernet_for(settings.SECRET_KEY).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Nao foi possivel descriptografar o segredo; a SECRET_KEY mudou desde que foi salvo."
        ) from exc
    return encrypt_secret(plaintext)
