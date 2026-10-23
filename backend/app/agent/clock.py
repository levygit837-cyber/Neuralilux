"""Hora local da Company e tempo decorrido, em português, para o system prompt e as Sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from app.agent.business_hours import describe_opening, is_open_at, next_opening
from app.models import Company
from app.models.company import DEFAULT_SESSION_TIMEOUT_MINUTES

logger = structlog.get_logger()

DEFAULT_TIMEZONE = "America/Sao_Paulo"
WEEKDAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


def company_zone(company: Company) -> ZoneInfo:
    try:
        return ZoneInfo(company.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):  # ValueError: chave com caminho ("../x", "/etc/x") ou vazia
        logger.warning("Unknown company timezone, using default", company_id=company.id, timezone=company.timezone)
        return ZoneInfo(DEFAULT_TIMEZONE)


def as_utc(value: datetime) -> datetime:
    """O SQLite devolve datetimes sem fuso; no banco todos são UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def format_local(now: datetime, zone: ZoneInfo) -> str:
    local = as_utc(now).astimezone(zone)
    return f"{WEEKDAYS[local.weekday()]}, {local:%d/%m/%Y}, {local:%H:%M} (fuso {zone.key})"


def humanize_elapsed(elapsed: timedelta) -> str:
    minutes = int(elapsed.total_seconds() // 60)
    if minutes < 1:
        return "menos de 1 minuto"
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 24 * 60:
        hours, rest = divmod(minutes, 60)
        return f"{hours} h" if rest == 0 else f"{hours} h {rest} min"
    days = minutes // (24 * 60)
    return "1 dia" if days == 1 else f"{days} dias"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def time_context(
    company: Company, now: datetime, previous_at: datetime | None, session_started_at: datetime | None
) -> str:
    """Bloco do system prompt com a data/hora local da Company e há quanto tempo foi a Message anterior."""
    lines = [f"Agora é {format_local(now, company_zone(company))}."]
    if previous_at is None:
        lines.append("Esta é a primeira mensagem deste cliente.")
    else:
        lines.append(f"A mensagem anterior do atendimento foi há {humanize_elapsed(as_utc(now) - as_utc(previous_at))}.")
        if session_started_at is not None and as_utc(previous_at) < as_utc(session_started_at):
            lines.append(
                "Este é um novo atendimento depois de uma pausa longa: cumprimente conforme o horário e "
                "não assuma que o assunto anterior continua. O que veio antes está no resumo e em `buscar_historico`."
            )
    lines.append('Use essa data e hora para saudação ("bom dia", "boa noite") e para "hoje", "ontem" e "amanhã".')
    return "\n".join(lines)


def opening_notice(company: Company, now: datetime) -> str:
    """Estado aberto/fechado da Company para o bloco do Turn; vazio se não há horários cadastrados.

    Usa as mesmas funções de `finalizar` e `info_empresa` (`is_open_at`, `next_opening`). Fechada, diz também se a
    abertura cai antes de a Session atual acabar por inatividade (ADR 0007): o ramo decide o que isso significa.
    """
    local_now = as_utc(now).astimezone(company_zone(company))
    is_open = is_open_at(company.business_hours, local_now)
    if is_open is None:
        return ""
    if is_open:
        return "A empresa está aberta agora."
    opening = next_opening(company.business_hours, local_now)
    if opening is None:
        return "A empresa está fechada agora e não tem próxima abertura cadastrada."
    timeout = timedelta(minutes=company.session_timeout_minutes or DEFAULT_SESSION_TIMEOUT_MINUTES)
    wait = opening - local_now
    verdict = "antes" if wait <= timeout else "depois"
    return (
        f"A empresa está fechada agora e abre {describe_opening(opening, local_now)} (daqui a {humanize_elapsed(wait)}). "
        f"O atendimento atual se encerra após {humanize_elapsed(timeout)} sem mensagens: "
        f"a abertura cai {verdict} desse prazo."
    )
