"""Horário de funcionamento da Company: aberto agora, próxima janela e fuso.

`Company.business_hours` é `{"mon": [["11:00", "23:00"]], ...}`, no fuso `Company.timezone`.
As funções puras recebem o "agora" já convertido para o fuso da Company (`app.agent.clock.company_zone`).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

# Ordem de `datetime.weekday()`: segunda = 0.
DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")
WEEKDAY_NAMES = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def parse_clock(value: Any) -> int:
    """Minutos desde 00:00 de um `HH:MM` estrito (00:00 a 23:59). Único parser: o painel valida com ele
    o que `is_open_at` e `next_opening` leem depois, então os dois sempre concordam."""
    if not isinstance(value, str) or not _CLOCK.match(value):
        raise ValueError(f"Horário inválido: {value!r}; use HH:MM, de 00:00 a 23:59.")
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _intervals(raw: Any) -> list[tuple[int, int]]:
    return [(parse_clock(start), parse_clock(end)) for start, end in (raw or [])]


def is_open_at(hours: dict[str, list[list[str]]] | None, local_now: datetime) -> bool | None:
    """True/False se a Company está aberta em `local_now` (já no fuso dela); None se não há horários.

    Intervalo cujo fim é menor ou igual ao início cruza a meia-noite (`["18:00", "02:00"]`);
    fim `"00:00"` significa "até o fim do dia". Dia ausente no dicionário = fechado.
    """
    if not hours:
        return None
    now = local_now.hour * 60 + local_now.minute
    weekday = local_now.weekday()

    for start, end in _intervals(hours.get(DAY_KEYS[weekday])):
        if (start <= now < end) if end > start else (now >= start):
            return True
    # Sobra de ontem: intervalo que cruzou a meia-noite e ainda não terminou.
    for start, end in _intervals(hours.get(DAY_KEYS[(weekday - 1) % 7])):
        if end <= start and now < end:
            return True
    return False


def next_opening(hours: dict[str, list[list[str]]] | None, local_now: datetime) -> datetime | None:
    """Início da próxima janela de atendimento depois de `local_now`; None se não há nenhuma.

    Procura hoje e os 7 dias seguintes (hoje de novo, na semana que vem, cobre o caso de um único dia aberto).
    """
    if not hours:
        return None
    for offset in range(8):
        day = local_now + timedelta(days=offset)
        for start, _end in sorted(_intervals(hours.get(DAY_KEYS[day.weekday()]))):
            opening = day.replace(hour=start // 60, minute=start % 60, second=0, microsecond=0)
            if opening > local_now:
                return opening
    return None


def describe_opening(opening: datetime, local_now: datetime) -> str:
    """Frase curta para o Contact: "hoje às 18:00", "amanhã às 09:30", "quinta-feira às 14:00"."""
    clock = f"{opening:%H:%M}"
    days_ahead = (opening.date() - local_now.date()).days
    if days_ahead <= 0:
        return f"hoje às {clock}"
    if days_ahead == 1:
        return f"amanhã às {clock}"
    name = WEEKDAY_NAMES[opening.weekday()]
    if days_ahead < 7:
        return f"{name} às {clock}"
    return f"{name} ({opening:%d/%m}) às {clock}"

