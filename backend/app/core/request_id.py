"""Request id: cada requisição HTTP tem um id, no cabeçalho `X-Request-ID` da resposta e em todo log dela."""
import re
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
# Só o que cabe com segurança num log e num cabeçalho: sem espaço, quebra de linha nem aspas.
_VALID = re.compile(r"[A-Za-z0-9._-]{1,64}")

logger = structlog.get_logger()


def valid_request_id(value: str | None) -> bool:
    return value is not None and _VALID.fullmatch(value) is not None


class RequestIdMiddleware:
    """Aceita o `X-Request-ID` do chamador se tiver formato e tamanho válidos (1 a 64 de `[A-Za-z0-9._-]`); senão gera
    um novo. Devolve na resposta e põe em `contextvars`, de onde o `merge_contextvars` do structlog o leva a cada log.

    Registrado por último, logo é o middleware mais externo: a resposta 403 do `OriginGuardMiddleware` e as do CORS
    também levam o id. Uma exceção não tratada vira 500 aqui, com o traceback logado já com o id.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        sent = Headers(scope=scope).get(HEADER)
        request_id = sent if valid_request_id(sent) else uuid.uuid4().hex
        started = False

        async def send_with_id(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            logger.exception("Unhandled error", method=scope["method"], path=scope["path"])
            if started:
                raise
            await JSONResponse({"detail": "Internal Server Error"}, status_code=500)(scope, receive, send_with_id)
        finally:
            structlog.contextvars.clear_contextvars()
