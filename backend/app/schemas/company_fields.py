"""Validação dos campos de configuração da Company que o painel edita: horários, chave Pix e texto livre.

O que passa aqui é o que `info_empresa`, `is_open_at` e o Pix do fechamento leem do banco; um valor
que eles não sabem interpretar tem de ser recusado na entrada, não descoberto no meio de um Turn.
"""

from __future__ import annotations

import re
from typing import Any

from app.agent.business_hours import DAY_KEYS

_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_MINUTES_PER_DAY = 24 * 60
_MINUTES_PER_WEEK = 7 * _MINUTES_PER_DAY

# Campo EMV 26 do BR Code: "br.gov.bcb.pix" (18 caracteres com o cabeçalho) + chave, no máximo 99.
PIX_KEY_MAX_LENGTH = 77
_EMAIL_KEY = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_KEY = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_PHONE_KEY = re.compile(r"^\+55\d{10,11}$")
_TAX_ID_KEY = re.compile(r"^(\d{11}|\d{14})$")
_FORMATTED_TAX_ID = re.compile(r"^(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$")


def blank_to_none(value: Any) -> Any:
    """Texto só com espaços vira `None` (campo limpo); outros textos são aparados."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _clock_minutes(value: Any) -> int:
    if not isinstance(value, str) or not _CLOCK.match(value):
        raise ValueError(f"Horário inválido: {value!r}; use HH:MM, de 00:00 a 23:59.")
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def validate_business_hours(raw: Any) -> dict[str, list[list[str]]] | None:
    """`{"mon": [["11:00", "14:00"], ["18:00", "02:00"]], ...}` ou `None` (sem horários).

    Dia ausente ou lista vazia = fechado. Fim menor ou igual ao início cruza a meia-noite e vale
    até esse horário do dia seguinte (`"00:00"` é o fim do dia). Janelas não podem se sobrepor,
    inclusive a que atravessa a virada de domingo para segunda.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("Horários devem ser um objeto com os dias da semana.")

    cleaned: dict[str, list[list[str]]] = {}
    windows: list[tuple[int, int]] = []  # na linha do tempo da semana, em minutos
    for day, intervals in raw.items():
        if day not in DAY_KEYS:
            raise ValueError(f"Dia inválido: {day!r}; use {', '.join(DAY_KEYS)}.")
        if not isinstance(intervals, list):
            raise ValueError(f"Os horários de {day} devem ser uma lista de [abre, fecha].")
        cleaned[day] = []
        for interval in intervals:
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError(f"Cada intervalo de {day} deve ter abertura e fechamento.")
            start, end = _clock_minutes(interval[0]), _clock_minutes(interval[1])
            if start == end:
                raise ValueError(f"Intervalo de {day} começa e termina às {interval[0]}.")
            length = end - start if end > start else end + _MINUTES_PER_DAY - start
            begin = DAY_KEYS.index(day) * _MINUTES_PER_DAY + start
            if begin + length > _MINUTES_PER_WEEK:  # passa de domingo para segunda
                windows.append((begin, _MINUTES_PER_WEEK))
                windows.append((0, begin + length - _MINUTES_PER_WEEK))
            else:
                windows.append((begin, begin + length))
            cleaned[day].append([interval[0], interval[1]])

    windows.sort()
    for (_, previous_end), (next_start, _) in zip(windows, windows[1:]):
        if next_start < previous_end:
            raise ValueError("Há horários que se sobrepõem.")
    return cleaned


def validate_pix_key(value: Any) -> str | None:
    """Chave Pix de qualquer tipo: e-mail, aleatória (UUID), celular (+55...), CPF ou CNPJ."""
    value = blank_to_none(value)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Chave Pix inválida.")
    if len(value) > PIX_KEY_MAX_LENGTH:
        raise ValueError(f"Chave Pix longa demais; o máximo é {PIX_KEY_MAX_LENGTH} caracteres.")
    if _FORMATTED_TAX_ID.match(value):
        return re.sub(r"\D", "", value)
    phone = re.sub(r"[\s()-]", "", value)
    if _PHONE_KEY.match(phone):
        return phone
    if _TAX_ID_KEY.match(value) or _UUID_KEY.match(value) or _EMAIL_KEY.match(value):
        return value
    raise ValueError("Chave Pix inválida; use e-mail, CPF, CNPJ, celular com +55 ou chave aleatória.")
