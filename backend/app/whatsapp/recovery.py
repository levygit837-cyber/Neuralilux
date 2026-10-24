"""Retoma as Messages do Contact que ficaram `pending` sem resposta (worker caiu, Turn falhou, shutdown).

Roda na subida do worker e a cada `TURN_RECOVERY_INTERVAL_SECONDS`. Reaproveita as regras que já existem (Handoff,
grupo, `from_me`, `@lid`, `agent_enabled`): as estáticas estão em `turn_state.skip_reason` e as que dependem do estado
atual (Agent ligado, Agent existente, texto) em `TurnRunner._admit`, por onde toda Message retomada passa.

Por Conversation, em ordem:

1. Mais velha que `TURN_RECOVERY_MAX_AGE_SECONDS` -> `skipped: stale` (responder agora seria estranho).
2. Já respondida: existe Message `from_me` gravada depois que o Turn dela começou (a resposta saiu, o worker caiu antes de
   anotar) -> `answered: sent_elsewhere`, sem reenviar. O eco do webhook faz o mesmo em `consumer.py`.
3. Conversation em Handoff -> `skipped: handoff`.
4. As que sobram viram **um** Turn (sem nova pausa), como se tivessem chegado juntas.

Vários workers: cada Message é tomada com um UPDATE atômico (`turn_state.claim`, compare-and-set sobre
`turn_claimed_at`). Dois workers que varrem ao mesmo tempo veem as mesmas pendentes, mas só um UPDATE casa; o outro
recebe zero linhas e larga a Message. Não precisa de `FOR UPDATE SKIP LOCKED`, e a mesma consulta roda no SQLite dos testes.
"""
import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Conversation, Message
from app.whatsapp import turn_state
from app.whatsapp.turn_batcher import Entry
from app.whatsapp.turn_runner import TurnRunner, Work
from app.whatsapp.webhook_parser import parsed_from_stored

logger = structlog.get_logger()


class Recovery:
    def __init__(
        self, runner: TurnRunner, session_factory: Callable[[], Session], now: Callable[[], datetime] = turn_state.now
    ) -> None:
        self._runner = runner
        self._session_factory = session_factory
        self._now = now

    async def sweep(self) -> int:
        """Uma varredura. Devolve quantas Messages foram entregues a um Turn."""
        at = self._now()
        db = self._session_factory()
        try:
            by_conversation: dict[str | None, list[Message]] = defaultdict(list)
            for message in turn_state.recoverable(db, at):
                if not self._runner.is_active(message.id):
                    by_conversation[message.conversation_id].append(message)
            batches = [works for messages in by_conversation.values() if (works := self._triage(db, messages, at))]
        finally:
            db.close()
        for works in batches:
            self._runner.spawn(works, recovered=True)
        count = sum(len(works) for works in batches)
        if count:
            logger.info("Pending messages resumed", messages=count, conversations=len(batches))
        return count

    def resume_redelivered(self, db: Session, message: Message) -> bool:
        """A Message chegou de novo do broker e está `pending`: quem a recebeu antes morreu antes de confirmar."""
        at = self._now()
        if self._runner.is_active(message.id) or not turn_state.takeable(
            message.turn_reason, message.turn_claimed_at, at, redelivered=True
        ):
            return False
        works = self._triage(db, [message], at)
        if works:
            self._runner.spawn(works, recovered=True)
        return bool(works)

    def _triage(self, db: Session, messages: list[Message], at: datetime) -> list[Work]:
        """Fecha as que não devem mais ser respondidas e toma as demais. Mesma Conversation, ordem de chegada."""
        conversation = db.get(Conversation, messages[0].conversation_id) if messages[0].conversation_id else None
        oldest = at - timedelta(seconds=settings.TURN_RECOVERY_MAX_AGE_SECONDS)
        live: list[Message] = []
        for message in messages:
            if conversation is None:
                reason = turn_state.SKIP_GONE
            elif turn_state.aware(message.timestamp) < oldest:
                reason = turn_state.SKIP_STALE
            else:
                reason = turn_state.skip_reason(message.is_from_me, message.remote_jid, message.timestamp, None)
            if reason:
                self._settle(db, [message], turn_state.SKIPPED, reason)
            else:
                live.append(message)
        if conversation is None or not live:
            return []

        began = [m for m in live if turn_state.started(m.turn_reason, m.turn_claimed_at)]
        if began and turn_state.sent_since(db, conversation.id, min(turn_state.aware(m.turn_claimed_at) for m in began)):
            self._settle(db, began, turn_state.ANSWERED, turn_state.SENT_ELSEWHERE)
            live = [m for m in live if m not in began]
        if live and db.query(Conversation.human_in_loop).filter(Conversation.id == conversation.id).scalar():
            self._settle(db, live, turn_state.SKIPPED, turn_state.SKIP_HANDOFF)
            return []

        won = turn_state.claim(db, [(m.id, m.turn_claimed_at) for m in live], at, turn_state.QUEUED)
        return [
            Work(
                instance_id=m.instance_id,
                conversation_id=conversation.id,
                contact_id=conversation.contact_id,
                entry=Entry(m.id, parsed.text, turn_state.aware(m.timestamp), won[m.id]),
                parsed=parsed,
            )
            for m in live
            if m.id in won
            for parsed in (parsed_from_stored(m.message_type, m.content),)
        ]

    @staticmethod
    def _settle(db: Session, messages: list[Message], state: str, reason: str) -> None:
        turn_state.settle(db, [(m.id, m.turn_claimed_at) for m in messages], state, reason)

    async def run_forever(self) -> None:
        """Varre na subida e a cada `TURN_RECOVERY_INTERVAL_SECONDS`, até ser cancelada."""
        while True:
            try:
                await self.sweep()
            except Exception:
                logger.exception("Turn recovery sweep failed")
            await asyncio.sleep(settings.TURN_RECOVERY_INTERVAL_SECONDS)
