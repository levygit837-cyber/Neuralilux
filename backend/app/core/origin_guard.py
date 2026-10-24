"""Proteção CSRF das mutações: o `Origin` de um navegador tem de ser um dos `CORS_ORIGINS` (ADR 0008)."""
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class OriginGuardMiddleware:
    """Recusa com 403 mutação (método fora de GET/HEAD/OPTIONS) cujo `Origin` não esteja em `CORS_ORIGINS`.

    Navegadores mandam `Origin` em toda mutação, inclusive `Origin: null` (recusado aqui, por não estar na
    lista). Chamadores que não são navegador (webhook da Evolution, scripts e e2e com Bearer) não mandam
    `Origin` e passam: sem navegador não há cookie de sessão a abusar. O `SameSite=Lax` do cookie sozinho não
    basta, porque outras portas e subdomínios do mesmo site também enviam o cookie.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in _SAFE_METHODS:
            origin = Headers(scope=scope).get("origin")
            if origin is not None and origin not in settings.CORS_ORIGINS:
                response = JSONResponse({"detail": "Origin not allowed"}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
