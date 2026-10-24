"""Roda os Turns fora da entrega do webhook, com concorrência limitada, e mantém o estado durável das Messages.

A entrega do webhook só grava a Message (`turn_state = pending`) e confirma ao broker; o Turn roda numa task daqui. Assim
a entrega nunca espera o Gateway: o `prefetch` do RabbitMQ não é consumido por Turns lentos e um `connection.update` não
fica atrás de 20 Conversations esperando o modelo. Os Turns concorrentes são limitados por `TURN_CONCURRENCY`; a pausa do
debounce fica fora desse limite (só ocupa vaga quem já vai falar com o Gateway).

O que impede a perda: a Message fica `pending` no banco até um Turn terminar (`turn_state.py`). Se este processo parar
no meio, `recovery.py` retoma. Estados e regras de posse: `turn_state.py`.
"""
import asyncio
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
from typing import Iterator

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.config import settings
from app.models import Contact, Conversation, Instance
from app.services.agent_service import resolve_turn_agent
from app.whatsapp import turn_state
from app.whatsapp.agent_turn import FAILED, GONE, NO_REPLY, REPLIED, run_agent_turn
from app.whatsapp.sender import send_and_persist
from app.whatsapp.turn_batcher import Entry, Group, Hold, TurnBatcher
from app.whatsapp.webhook_parser import ParsedContent

logger = structlog.get_logger()

# Resposta fixa para mídia sem texto: o Agent não é chamado.
MEDIA_REPLY = "Por enquanto só consigo ler mensagens de texto. Pode me escrever o que você precisa?"

_OUTCOMES = {
    REPLIED: (turn_state.ANSWERED, turn_state.REPLIED),
    NO_REPLY: (turn_state.ANSWERED, turn_state.NO_REPLY),
    GONE: (turn_state.SKIPPED, turn_state.SKIP_GONE),
}


@dataclass(frozen=True)
class Work:
    """Uma Message do Contact a responder. `entry.claim` é a posse que quem entrega viu (compare-and-set)."""

    instance_id: str
    conversation_id: str
    contact_id: str
    entry: Entry
    parsed: ParsedContent


class TurnRunner:
    def __init__(self, session_factory: Callable[[], Session], spawn_summary: Callable[[str], None]) -> None:
        self._session_factory = session_factory
        self._spawn_summary = spawn_summary
        self.batcher = TurnBatcher()
        self._slots = asyncio.Semaphore(max(1, settings.TURN_CONCURRENCY))
        self.tasks: set[asyncio.Task] = set()
        self._queued: dict[str, datetime | None] = {}  # Message.id -> posse; esperando a pausa do Contact ou uma vaga
        self._running: dict[str, datetime] = {}  # Message.id -> posse; Turn em andamento
        self._missing_agent_logged: set[str] = set()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def is_active(self, message_id: str) -> bool:
        return message_id in self._queued or message_id in self._running

    @property
    def running_ids(self) -> set[str]:
        return set(self._running)

    def spawn(self, works: list[Work], hold: Hold | None = None, *, recovered: bool = False) -> None:
        """Entrega as Messages de uma Conversation ao agrupamento, numa task rastreada. Volta na hora.

        `hold`: o da Message recém-gravada; é solto quando ela chega ao agrupamento. `recovered`: Messages que já
        esperaram (recuperação) viram um único Turn, sem nova pausa.
        """
        for work in works:
            self._queued[work.entry.message_id] = work.entry.claim
        task = asyncio.create_task(self._submit(works, hold, recovered))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _submit(self, works: list[Work], hold: Hold | None, recovered: bool) -> None:
        first = works[0]
        log = logger.bind(instance_id=first.instance_id, conversation_id=first.conversation_id)
        try:
            agent_id, entries = await self._admit(works, log)
            if entries:
                window, max_wait, grouped = (
                    (0.0, None, True) if recovered else (settings.DEBOUNCE_SECONDS, settings.DEBOUNCE_MAX_WAIT_SECONDS, None)
                )
                await self.batcher.submit(
                    first.conversation_id, entries, partial(self._run, first, agent_id), window, hold, max_wait, grouped
                )
        except Exception:
            # Nunca derruba o worker: a Message segue pendente e a recuperação tenta de novo quando a posse vencer.
            log.exception("Unexpected error processing message with agent")
            for work in works:
                self._queued.pop(work.entry.message_id, None)
        finally:
            if hold is not None:
                hold.release()  # idempotente: o `submit` já a soltou; os caminhos que saem antes dele soltam aqui

    def _finish(self, db: Session, works: Iterable[Work], state: str, reason: str) -> None:
        turn_state.settle(db, [(w.entry.message_id, w.entry.claim) for w in works], state, reason)
        for work in works:
            self._queued.pop(work.entry.message_id, None)

    async def _admit(self, works: list[Work], log) -> tuple[str | None, list[Entry]]:
        """Regras de skip que dependem do estado atual (Agent ligado, Agent existente, texto). Devolve o que vai a Turn."""
        first = works[0]
        with self._session() as db:
            instance = db.get(Instance, first.instance_id)
            conversation = db.get(Conversation, first.conversation_id)
            contact = db.get(Contact, first.contact_id)
            if instance is None or conversation is None or contact is None:
                self._finish(db, works, turn_state.SKIPPED, turn_state.SKIP_GONE)
                return None, []
            if not instance.agent_enabled:
                log.info("Agent disabled for this instance")
                self._finish(db, works, turn_state.SKIPPED, turn_state.SKIP_AGENT_DISABLED)
                return None, []
            agent = resolve_turn_agent(db, instance)
            if agent is None:
                # Um erro por Instance até o worker reiniciar: sem Agent, toda mensagem cairia aqui.
                if instance.id not in self._missing_agent_logged:
                    self._missing_agent_logged.add(instance.id)
                    log.error(
                        "No active Agent for this Instance or its Company; messages are not answered. "
                        "Run scripts/seed_data.py or create the Company's Agent",
                        company_id=instance.company_id,
                    )
                self._finish(db, works, turn_state.SKIPPED, turn_state.SKIP_NO_AGENT)
                return None, []
            self._missing_agent_logged.discard(instance.id)

            entries: list[Entry] = []
            for work in works:
                if work.parsed.is_media and not work.parsed.text.strip():
                    await self._reply_to_media(db, instance, conversation, contact, work)
                elif not work.parsed.text.strip():
                    log.info("Message without text, Agent not called", message_type=work.parsed.message_type)
                    self._finish(db, [work], turn_state.SKIPPED, turn_state.SKIP_NO_TEXT)
                else:
                    entries.append(work.entry)
            return agent.id, entries

    async def _reply_to_media(
        self, db: Session, instance: Instance, conversation: Conversation, contact: Contact, work: Work
    ) -> None:
        message_id = work.entry.message_id
        won = turn_state.claim(db, [(message_id, work.entry.claim)], turn_state.now())
        self._queued.pop(message_id, None)
        if message_id not in won:
            return
        mine = [(message_id, won[message_id])]
        self._running[message_id] = won[message_id]
        try:
            if executor._in_handoff(db, conversation.id):
                turn_state.settle(db, mine, turn_state.SKIPPED, turn_state.SKIP_HANDOFF)
            else:
                await send_and_persist(db, instance, conversation, contact, MEDIA_REPLY)
                turn_state.settle(db, mine, turn_state.ANSWERED, turn_state.MEDIA_REPLY)
        except asyncio.CancelledError:
            db.rollback()
            turn_state.release(db, mine)
            raise
        except Exception:
            db.rollback()
            turn_state.fail(db, mine)
            raise
        finally:
            self._running.pop(message_id, None)

    async def _run(self, work: Work, agent_id: str, group: Group) -> None:
        """Um Turn do agrupamento: espera vaga, toma as Messages, roda, grava o desfecho."""
        async with self._slots:
            at = turn_state.now()
            with self._session() as db:
                won = turn_state.claim(db, [(e.message_id, e.claim) for e in group.entries], at)
            for entry in group.entries:
                self._queued.pop(entry.message_id, None)
            entries = tuple(replace(e, claim=at) for e in group.entries if e.message_id in won)
            if not entries:
                logger.info("Messages taken by another worker, Turn dropped", conversation_id=work.conversation_id)
                return
            mine = [(e.message_id, at) for e in entries]
            self._running.update(dict(mine))
            try:
                outcome = await run_agent_turn(
                    self._session_factory, work.instance_id, work.conversation_id, work.contact_id, agent_id,
                    self._spawn_summary, Group(entries, group.deferred_ids),
                )
            except asyncio.CancelledError:
                self._close(mine, turn_state.release)
                raise
            else:
                if outcome == FAILED:
                    self._close(mine, turn_state.fail)
                else:
                    state, reason = _OUTCOMES[outcome]
                    self._close(mine, partial(turn_state.settle, state=state, reason=reason))
            finally:
                for message_id, _ in mine:
                    self._running.pop(message_id, None)

    def _close(self, claims: list[turn_state.Claim], action: Callable[..., None]) -> None:
        with self._session() as db:
            action(db, claims)

    async def shutdown(self, timeout: float) -> None:
        """Espera os Turns em voo até `timeout`; cancela o resto. Quem não terminou volta a ficar disponível à recuperação."""
        pending = {task for task in self.tasks if not task.done()}
        if pending:
            _, unfinished = await asyncio.wait(pending, timeout=timeout)
            for task in unfinished:
                task.cancel()
            if unfinished:
                logger.warning("Turns cancelled at shutdown, Messages stay pending", turns=len(unfinished), timeout=timeout)
                await asyncio.gather(*unfinished, return_exceptions=True)
        if self._queued or self._running:
            with self._session() as db:
                turn_state.unclaim(db, list(self._queued.items()))
                turn_state.release(db, list(self._running.items()))
            self._queued.clear()
            self._running.clear()

    async def drain(self) -> None:
        """Espera os Turns em andamento terminarem (testes e shutdown sem prazo)."""
        while pending := {task for task in self.tasks if not task.done()}:
            await asyncio.wait(pending)
