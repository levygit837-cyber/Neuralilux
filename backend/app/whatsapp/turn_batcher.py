"""Agrupa as Messages picadas de uma Conversation num único Turn.

A primeira Message de uma rajada vira a "líder": espera a Conversation ficar `window` segundos sem Message
nova e roda o Turn com o texto de todas. As seguintes só entram na fila e voltam na hora, então o broker as
confirma sem esperar o Turn. Message que chega durante o Turn fica na fila e é tratada no Turn seguinte, depois
de outra pausa, na mesma líder: nunca há dois Turns da mesma Conversation ao mesmo tempo.
Conversations diferentes têm filas independentes e rodam em paralelo.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime

import structlog

logger = structlog.get_logger()

TurnRunner = Callable[[str, datetime], Awaitable[None]]


class _Batch:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.first_received_at: datetime | None = None  # a mais antiga das Messages do grupo
        self.last_at = 0.0

    def add(self, text: str, received_at: datetime, now: float) -> None:
        self.texts.append(text)
        if self.first_received_at is None or received_at < self.first_received_at:
            self.first_received_at = received_at
        self.last_at = now


class TurnBatcher:
    def __init__(
        self,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._monotonic = monotonic
        self._sleep = sleep
        self._batches: dict[str, _Batch] = {}

    @property
    def active(self) -> set[str]:
        """Conversations com uma líder esperando ou rodando um Turn."""
        return set(self._batches)

    async def submit(self, key: str, text: str, received_at: datetime, run: TurnRunner, window: float) -> None:
        """Enfileira `text`. Quem abre a rajada só volta depois que os Turns dela terminam; as demais voltam na hora.

        `run` recebe os textos juntos, um por linha, e o `received_at` da Message mais antiga do grupo: é o
        instante que os Packs usam para saber se o Contact já tinha visto a resposta anterior. Erro do Turn é logado e não sobe: a entrega não deve ser
        reprocessada (a resposta pode já ter saído), e as Messages que chegaram durante o Turn seguem para o próximo.
        """
        batch = self._batches.get(key)
        if batch is not None:
            batch.add(text, received_at, self._monotonic())
            return

        batch = self._batches[key] = _Batch()
        batch.add(text, received_at, self._monotonic())
        try:
            while batch.texts:
                await self._wait_for_pause(batch, window)
                joined, first_at = "\n".join(batch.texts), batch.first_received_at
                batch.texts, batch.first_received_at = [], None
                try:
                    await run(joined, first_at)
                except Exception:
                    logger.exception("Turn failed in batcher", conversation_key=key)
        finally:
            del self._batches[key]

    async def _wait_for_pause(self, batch: _Batch, window: float) -> None:
        while (remaining := batch.last_at + window - self._monotonic()) > 0:
            await self._sleep(remaining)
