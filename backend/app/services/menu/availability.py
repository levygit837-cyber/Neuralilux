"""Disponibilidade de Catalog Items com horário próprio (ex.: pizza só à noite).

O JSON do cardápio traz as janelas de venda do item em `items_availability` (`weekday`: 1 = domingo ... 7 = sábado;
`period_end` inclusivo, "23:59" = até o fim do dia) e marca `is_available=false` no item que estava fora da janela no
momento da captura (`source.fetched_at_utc`). Esse `false` é transitório: gravá-lo em `MenuItem.is_available`
esconderia o item do Agent para sempre. Já o `false` de um item pausado com a captura dentro da janela é real.

As janelas são lidas com as mesmas regras de `Company.business_hours` (`app.agent.business_hours`): fim antes do
início cruza a meia-noite e vale na madrugada seguinte.
"""

from __future__ import annotations

from datetime import datetime, tzinfo
from typing import Any

from app.agent.business_hours import DAY_KEYS, describe_opening, is_open_at, next_opening, parse_clock


def item_hours(raw: dict[str, Any] | None) -> dict[str, list[list[str]]]:
    """Janelas do item no formato de `Company.business_hours`, com o fim convertido para exclusivo.

    Janela com horário inválido é ignorada: o item não fica escondido por um dado quebrado do cardápio.
    """
    hours: dict[str, list[list[str]]] = {}
    for window in (raw or {}).get("items_availability") or []:
        try:
            day = DAY_KEYS[(int(window["weekday"]) - 2) % 7]
            start = parse_clock(window.get("period_start") or "00:00")
            end = (parse_clock(window.get("period_end") or "23:59") + 1) % (24 * 60)
        except (KeyError, TypeError, ValueError):
            continue
        hours.setdefault(day, []).append([_clock(start), _clock(end)])
    return hours


def capture_time(payload: dict[str, Any], zone: tzinfo) -> datetime | None:
    """Momento da captura do cardápio no fuso da Company; `None` se o JSON não diz ou diz algo ilegível."""
    raw = (payload.get("source") or {}).get("fetched_at_utc")
    try:
        captured = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return captured.astimezone(zone) if captured.tzinfo else None


def item_is_available(raw: dict[str, Any], captured_local: datetime | None) -> bool:
    """`False` quando o item está fora do cardápio de fato; `True` se o `false` vem só do horário da captura.

    Sem o horário da captura não dá para separar os dois casos, e o `false` do JSON vale.
    """
    flag = bool(raw.get("is_available_if_active", raw.get("is_available", True)))
    if flag or captured_local is None:
        return flag
    return is_open_at(item_hours(raw) or None, captured_local) is False


def schedule_note(raw: dict[str, Any] | None, now_local: datetime) -> str | None:
    """Aviso quando o item tem janelas e `now_local` (fuso da Company) cai fora delas; `None` se pode vender agora."""
    hours = item_hours(raw)
    if is_open_at(hours or None, now_local) is not False:
        return None
    opening = next_opening(hours, now_local)
    return f"Fora do horário agora; disponível a partir de {describe_opening(opening, now_local)}."


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
