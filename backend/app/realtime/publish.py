"""Único caminho para publicar um evento realtime no bus (Turn, Tools, Handoff, webhook e envio).

O evento é um schema de `app.realtime.events`: construí-lo já o valida. No bus ele viaja como
`{"type": <nome do evento Socket.IO>, "payload": <campos>}`; o bus não aceita kwargs. Evento de UI nunca derruba
quem o publica: o estado do Turn ou do Handoff já está gravado, então falha no Redis só gera `warning`.
"""

from __future__ import annotations

import structlog

from app.realtime.event_bus import realtime_event_bus
from app.realtime.events import RealtimeEvent

logger = structlog.get_logger()


async def publish_event(event: RealtimeEvent) -> None:
    try:
        await realtime_event_bus.publish({"type": event.name, "payload": event.model_dump(mode="json")})
    except Exception:
        logger.warning("Realtime event publish failed", event_type=event.name, exc_info=True)
