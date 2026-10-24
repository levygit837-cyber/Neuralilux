"""Único caminho para publicar um evento realtime no bus (Turn, Tools do núcleo e Handoff).

O evento é um dict (`instance_name`, `type`, `payload`); o bus não aceita kwargs. Evento de UI nunca derruba
quem o publica: o estado do Turn ou do Handoff já está gravado, então falha no Redis só gera `warning`.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.realtime.event_bus import realtime_event_bus

logger = structlog.get_logger()


async def publish_event(event: dict[str, Any]) -> None:
    try:
        await realtime_event_bus.publish(event)
    except Exception as exc:
        logger.warning("Realtime event publish failed", event_type=event.get("type"), error=str(exc))
