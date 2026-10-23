"""O token do webhook vai na query string (ADR 0006): o access log do uvicorn não pode gravá-lo."""
import logging

from app.core.logging import RedactWebhookToken


def _render(path: str) -> str:
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "POST", path, "1.1", 200), None,
    )
    assert RedactWebhookToken().filter(record) is True  # nunca descarta a linha, só edita
    return record.getMessage()


def test_token_value_is_masked_in_the_webhook_path():
    line = _render("/api/v1/webhooks/evolution/messages-upsert?token=segredo-123&x=1")

    assert "segredo-123" not in line
    assert "token=***" in line and "x=1" in line


def test_other_paths_are_left_untouched():
    path = "/api/v1/instances?token_type=a&page=2"

    assert path in _render(path)

