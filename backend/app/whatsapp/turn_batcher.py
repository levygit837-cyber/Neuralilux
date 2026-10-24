"""Agrupa as Messages picadas de uma Conversation num único Turn.

A primeira Message de uma rajada vira a "líder": espera a Conversation ficar `window` segundos sem Message
nova e roda o Turn com o `Group` de todas. As seguintes só entram na fila e voltam na hora, então o broker as
confirma sem esperar o Turn. Message que chega durante o Turn fica na fila e é tratada no Turn seguinte, depois
de outra pausa, na mesma líder: nunca há dois Turns da mesma Conversation ao mesmo tempo.
Conversations diferentes têm filas independentes e rodam em paralelo.

`window <= 0` desliga o agrupamento: cada Message vira o seu próprio Turn, em ordem de chegada.

`max_wait` é o teto da espera: quem manda Messages a cada menos de `window` segundos não adia o Turn para sempre.
Passados `max_wait` segundos desde a primeira Message ainda sem Turn, a líder roda com o que já chegou; o que chegar
depois vira o Turn seguinte, com o teto contado de novo a partir da sua chegada.

O `Group` leva os ids das Messages: o Turn tira exatamente esses ids da Recent Window e os põe, juntos, no fim do
histórico. Para isso o grupo tem de estar fechado quando o Turn lê o contexto: o consumer pega um `Hold` assim
que grava a Message (sem `await` entre o commit e o `hold`) e o solta no `submit`. A líder não fecha o grupo
enquanto houver `Hold` aberto; uma Message já gravada entra, portanto, no grupo em curso ou no Turn seguinte, nunca
nos dois.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class Entry:
    message_id: str  # Message.id da linha gravada
    text: str
    received_at: datetime


@dataclass(frozen=True)
class Group:
    """As Messages de um Turn, na ordem de chegada."""

    entries: tuple[Entry, ...]
    # Messages já gravadas que ficaram na fila para o Turn seguinte (só sem agrupamento): este Turn não as vê.
    deferred_ids: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(entry.text for entry in self.entries)

    @property
    def message_ids(self) -> tuple[str, ...]:
        return tuple(entry.message_id for entry in self.entries)

    @property
    def received_at(self) -> datetime:
        """A da Message mais antiga: é o instante que os Packs usam para saber o que o Contact já tinha visto."""
        return min(entry.received_at for entry in self.entries)


TurnRunner = Callable[[Group], Awaitable[None]]


class Hold:
    """Message já gravada que ainda não chegou ao `submit`. `release` é idempotente."""

    def __init__(self, release: Callable[[], None]) -> None:
        self._release: Callable[[], None] | None = release

    def release(self) -> None:
        release, self._release = self._release, None
        if release is not None:
            release()


class _Holds:
    def __init__(self) -> None:
        self.count = 0
        self.idle = asyncio.Event()


class _Batch:
    def __init__(self) -> None:
        self.entries: list[Entry] = []
        self.first_at = 0.0  # chegada da Message mais antiga ainda sem Turn
        self.last_at = 0.0

    def add(self, entry: Entry, now: float) -> None:
        if not self.entries:
            self.first_at = now
        self.entries.append(entry)
        self.last_at = now

    def take(self, grouped: bool) -> Group:
        if grouped:
            taken, self.entries = tuple(self.entries), []
        else:
            taken = (self.entries.pop(0),)
        return Group(taken, tuple(entry.message_id for entry in self.entries))


class TurnBatcher:
    def __init__(
        self,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._monotonic = monotonic
        self._sleep = sleep
        self._batches: dict[str, _Batch] = {}
        self._holds: dict[str, _Holds] = {}

    @property
    def active(self) -> set[str]:
        """Conversations com uma líder esperando ou rodando um Turn."""
        return set(self._batches)

    def hold(self, key: str) -> Hold:
        """Marca uma Message gravada que ainda vai ser entregue ao `submit`. Chamar logo depois do commit, sem `await`."""
        state = self._holds.get(key)
        if state is None:
            state = self._holds[key] = _Holds()
        state.count += 1
        state.idle.clear()
        return Hold(lambda: self._release(key))

    def _release(self, key: str) -> None:
        state = self._holds[key]
        state.count -= 1
        if state.count == 0:
            del self._holds[key]
            state.idle.set()

    async def submit(
        self,
        key: str,
        entry: Entry,
        run: TurnRunner,
        window: float,
        hold: Hold | None = None,
        max_wait: float | None = None,
    ) -> None:
        """Enfileira `entry`. Quem abre a rajada só volta depois que os Turns dela terminam; as demais voltam na hora.

        `run` recebe o `Group` com as Messages juntas. `hold`, se houver, é solto junto com a entrada, sem `await`
        entre as duas coisas. Erro do Turn é logado e não sobe: a entrega não deve ser reprocessada (a resposta pode
        já ter saído), e as Messages que chegaram durante o Turn seguem para o próximo. `max_wait`: ver o topo do módulo.
        """
        batch = self._batches.get(key)
        if batch is not None:
            batch.add(entry, self._monotonic())
            if hold is not None:
                hold.release()
            return

        batch = self._batches[key] = _Batch()
        batch.add(entry, self._monotonic())
        if hold is not None:
            hold.release()
        try:
            while batch.entries:
                await self._wait_until_quiet(key, batch, window, max_wait)
                group = batch.take(window > 0)
                try:
                    await run(group)
                except Exception:
                    logger.exception("Turn failed in batcher", conversation_key=key)
        finally:
            del self._batches[key]

    async def _wait_until_quiet(self, key: str, batch: _Batch, window: float, max_wait: float | None) -> None:
        """Volta quando passou `window` sem Message nova (ou `max_wait` desde a primeira) e nenhuma Message gravada
        está a caminho do `submit`."""
        while True:
            while (remaining := self._remaining(batch, window, max_wait)) > 0:
                await self._sleep(remaining)
            holds = self._holds.get(key)
            if holds is None:
                return
            await holds.idle.wait()

    def _remaining(self, batch: _Batch, window: float, max_wait: float | None) -> float:
        now = self._monotonic()
        remaining = batch.last_at + window - now
        if max_wait is not None:
            remaining = min(remaining, batch.first_at + max_wait - now)
        return remaining
