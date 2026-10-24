"""Orçamento de retry de um Turn: vale para todas as chamadas ao Gateway do Turn, não para cada uma.

Sem ele, um Turn com 7 chamadas e 3 tentativas cada pode esperar o Gateway 20 vezes. O `RetryBudget` é criado
uma vez por Turn (`for_turn`) e viaja em `MessagesRequest.retry_budget`; o cliente gasta uma unidade a cada
retry e desiste, devolvendo o erro original, quando acabam os retries ou o tempo de espera.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class RetryBudget:
    retries: int  # retries que ainda podem acontecer no Turn
    wait_seconds: float  # segundos de espera que ainda podem ser gastos no Turn

    @classmethod
    def for_turn(cls) -> RetryBudget:
        return cls(retries=settings.TURN_RETRY_BUDGET, wait_seconds=settings.TURN_RETRY_WAIT_SECONDS)

    def reserve(self, wait: float) -> bool:
        """Gasta um retry e `wait` segundos de espera. False (sem gastar nada): o orçamento não cobre."""
        if self.retries <= 0 or wait > self.wait_seconds:
            return False
        self.retries -= 1
        self.wait_seconds -= wait
        return True
