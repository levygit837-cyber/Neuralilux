"""Cenário do Handoff: Company com horário, Instance, Conversation e eventos realtime capturados."""
import pytest

from app.services import handoff_service


@pytest.fixture
def realtime(monkeypatch):
    """Eventos que o serviço de Handoff publicaria no bus."""
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(handoff_service, "publish_event", capture)
    return published
