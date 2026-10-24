"""Hooks opcionais de um Pack: validação no registro e despacho tipado.

O conjunto é fechado (`PACK_HOOKS`: nome -> Protocol que fixa a assinatura). Um Pack com `on_*` fora dele (ex.:
`on_reply_deliverd`) seria um gancho que nunca dispara, e um gancho com a aridade errada só falharia no meio de um
Turn; por isso `validate_pack_hooks` recusa os dois ao registrar o Pack.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.contracts import PACK_HOOKS, Pack, ReplyDeliveredHook, SessionStartHook
from app.models import Conversation

HOOK_PREFIX = "on_"


class InvalidPackHookError(ValueError):
    """O Pack declara um gancho que o núcleo não conhece, ou um gancho conhecido com assinatura errada."""


def _expected_arity(hook_name: str) -> int:
    """Quantos argumentos o Protocol do gancho recebe (sem `self`)."""
    return len(inspect.signature(getattr(PACK_HOOKS[hook_name], hook_name)).parameters) - 1


def validate_pack_hooks(pack: Pack) -> None:
    pack_name = getattr(pack, "name", type(pack).__name__)
    for attr in dir(pack):
        if not attr.startswith(HOOK_PREFIX):
            continue
        if attr not in PACK_HOOKS:
            known = ", ".join(sorted(PACK_HOOKS))
            raise InvalidPackHookError(
                f"Pack {pack_name!r} declara o gancho desconhecido {attr!r}; os ganchos válidos são: {known}"
            )
        hook = getattr(pack, attr)
        if not callable(hook):
            raise InvalidPackHookError(f"Gancho {attr!r} do Pack {pack_name!r} não é chamável")
        expected = _expected_arity(attr)
        try:
            inspect.signature(hook).bind(*range(expected))
        except TypeError as exc:
            raise InvalidPackHookError(
                f"Gancho {attr!r} do Pack {pack_name!r} deve aceitar {expected} argumentos posicionais "
                f"(veja o Protocol em app.agent.contracts): {exc}"
            ) from exc


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
