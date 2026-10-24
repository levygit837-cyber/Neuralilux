"""Corpo da task de fundo que importa o histórico de uma Instance (disparada pelo consumer).

Abrir a Session, lê-la e fechá-la são chamadas bloqueantes: rodam em thread (`asyncio.to_thread`), uma de cada vez,
para o event loop do worker seguir livre enquanto o histórico é gravado.
"""
from __future__ import annotations

import asyncio
from typing import Callable

import structlog
from sqlalchemy.orm import Session

from app.models import Instance
from app.whatsapp import history_sync

logger = structlog.get_logger()


async def run(session_factory: Callable[[], Session], instance_id: str) -> None:
    """Importa o histórico da Instance numa Session própria. Falha só vai para o log: a task é de fundo."""
    sync_db = await asyncio.to_thread(session_factory)
    try:
        instance = await asyncio.to_thread(sync_db.get, Instance, instance_id)
        if instance is not None:
            await history_sync.sync_instance(sync_db, instance)
    except history_sync.SyncAlreadyRunning:
        logger.info("History sync skipped: another process is already importing", instance_id=instance_id)
    except Exception:
        logger.exception("History sync failed", instance_id=instance_id)
    finally:
        await asyncio.to_thread(sync_db.close)
