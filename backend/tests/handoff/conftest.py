"""Cenário do Handoff: Company com horário, Instance, Conversation e eventos realtime capturados."""
import pytest

from app.realtime.event_bus import realtime_event_bus


@pytest.fixture
def realtime(monkeypatch):
    """Eventos (`{"type", "payload"}`) que o Handoff publicaria no bus."""
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(realtime_event_bus, "publish", capture)
    return published
