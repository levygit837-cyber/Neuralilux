"""Disponibilidade de Catalog Items com horário próprio (ex.: pizza só à noite).

O JSON do cardápio marca `is_available=false` / `status=UNAVAILABLE` num item fora da janela no momento da
captura, mas traz as janelas em `items_availability` (`weekday`: 1 = domingo ... 7 = sábado). Esse `false` é
transitório: guardá-lo em `MenuItem.is_available` esconderia o item do Agent para sempre. O sync grava o item como
disponível e a janela é avaliada na hora da consulta com `schedule_note`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def item_is_available(raw: dict[str, Any]) -> bool:
    """`False` só quando o item está fora do cardápio de fato, não quando apenas está fora do horário."""
    flag = raw.get("is_available_if_active", raw.get("is_available", True))
    if not flag and raw.get("items_availability"):
        return True
    return bool(flag)


def schedule_note(raw: dict[str, Any] | None, now_local: datetime) -> str | None:
    """Aviso quando o item tem janelas e `now_local` (fuso da Company) cai fora delas; `None` se pode vender agora.

    Janela com fim antes do início cruza a meia-noite: a de sexta 18:00 às 02:00 ainda vale no sábado à 01:00.
    """
    windows = (raw or {}).get("items_availability") or []
    if not windows:
        return None
    weekday = (now_local.weekday() + 1) % 7 + 1
    yesterday = 7 if weekday == 1 else weekday - 1
    current = now_local.strftime("%H:%M")
    today = [w for w in windows if w.get("weekday") == weekday]
    for window in today:
        start, end = _bounds(window)
        if start <= current <= end or (end < start and current >= start):
            return None
    for window in (w for w in windows if w.get("weekday") == yesterday):
        start, end = _bounds(window)
        if end < start and current <= end:
            return None
    if not today:
        return "Não é vendido hoje."
    hours = ", ".join(f"{w.get('period_start')} às {w.get('period_end')}" for w in today)
    return f"Fora do horário agora; hoje só das {hours}."


def _bounds(window: dict[str, Any]) -> tuple[str, str]:
    return str(window.get("period_start") or "00:00"), str(window.get("period_end") or "23:59")
