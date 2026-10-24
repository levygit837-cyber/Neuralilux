"""Respostas das rotas de webhook da Evolution."""
from pydantic import BaseModel


class WebhookReceived(BaseModel):
    status: str
    event: str | None


class WebhookTestResponse(BaseModel):
    status: str
