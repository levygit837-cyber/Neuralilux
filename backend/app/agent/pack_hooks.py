"""Hooks opcionais de um Pack: validação no registro e despacho tipado.

O conjunto de nomes é fechado (`PACK_HOOK_NAMES`). Um Pack com `on_*` fora dele (ex.: `on_reply_deliverd`) seria
um gancho que nunca dispara, sem erro nenhum; por isso `validate_pack_hooks` recusa o Pack ao ser registrado.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.contracts import PACK_HOOK_NAMES, Pack, ReplyDeliveredHook, SessionStartHook
from app.models import Conversation

HOOK_PREFIX = "on_"


class InvalidPackHookError(ValueError):
    """O Pack declara um gancho que o núcleo não conhece, ou com um atributo que não é chamável."""


def validate_pack_hooks(pack: Pack) -> None:
    for attr in dir(type(pack)):
        if not attr.startswith(HOOK_PREFIX):
            continue
        if attr not in PACK_HOOK_NAMES:
            known = ", ".join(sorted(PACK_HOOK_NAMES))
            raise InvalidPackHookError(
                f"Pack {getattr(pack, 'name', type(pack).__name__)!r} declara o gancho desconhecido {attr!r}; "
                f"os ganchos válidos são: {known}"
            )
        if not callable(getattr(pack, attr)):
            raise InvalidPackHookError(f"Gancho {attr!r} do Pack {pack.name!r} não é chamável")


def run_session_start(packs: Iterable[Pack], db: Session, conversation: Conversation) -> None:
    for pack in packs:
        if isinstance(pack, SessionStartHook):
            pack.on_session_start(db, conversation)


def run_reply_delivered(
    packs: Iterable[Pack], db: Session, conversation: Conversation, turn_id: str, at: datetime
) -> None:
    for pack in packs:
        if isinstance(pack, ReplyDeliveredHook):
            pack.on_reply_delivered(db, conversation, turn_id, at)
