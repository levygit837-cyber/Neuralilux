"""Configuração de logs: structlog em JSON e máscara do token do webhook no access log do uvicorn."""
import logging
import re

import structlog

_WEBHOOK_TOKEN = re.compile(r"([?&]token=)[^&\s]*")


class RedactWebhookToken(logging.Filter):
    """Mascara `?token=` no access log do uvicorn: o token do webhook vai na URL (ADR 0006)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(_WEBHOOK_TOKEN.sub(r"\1***", a) if isinstance(a, str) else a for a in args)
        return True


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    logging.getLogger("uvicorn.access").addFilter(RedactWebhookToken())
