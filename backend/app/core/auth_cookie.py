"""Cookie de login do navegador: o JWT vai num cookie `httpOnly`, fora do alcance de JavaScript (ADR 0008)."""
from http.cookies import CookieError, SimpleCookie

from fastapi import Response

from app.core.config import settings

# O frontend lê o mesmo nome em `frontend/src/lib/constants.ts` (AUTH_COOKIE_NAME): mude os dois juntos.
AUTH_COOKIE_NAME = "nlx_auth"
_DEVELOPMENT = "development"


def _attributes() -> dict:
    """Atributos do cookie; os mesmos ao criar e ao apagar, senão o navegador não reconhece como o mesmo cookie."""
    return {
        "path": "/",
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "secure": settings.ENVIRONMENT != _DEVELOPMENT,
        "httponly": True,
        "samesite": "lax",
    }


def set_auth_cookie(response: Response, token: str) -> None:
    """Grava o JWT no cookie, com o mesmo prazo do próprio JWT."""
    response.set_cookie(AUTH_COOKIE_NAME, token, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, **_attributes())


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, **_attributes())


def auth_cookie_from_header(cookie_header: str | None) -> str | None:
    """Valor do cookie de login num cabeçalho `Cookie` bruto (o handshake do Socket.IO não passa pelo Starlette)."""
    if not cookie_header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except CookieError:
        return None
    morsel = jar.get(AUTH_COOKIE_NAME)
    return morsel.value if morsel and morsel.value else None
