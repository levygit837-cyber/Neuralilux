"""Relógio virtual dos testes de agrupamento: `sleep` só acorda quando o teste avança o tempo."""
import asyncio
import time

SETTLE_SPINS = 30
SETTLE_DEADLINE_SECONDS = 10.0

_in_flight = 0  # chamadas de `asyncio.to_thread` que ainda não voltaram (só o loop do teste mexe nele)


def track_threads(monkeypatch) -> None:
    """Conta as chamadas de `asyncio.to_thread` em voo, para o `settle` esperá-las. As threads continuam reais."""
    real_to_thread = asyncio.to_thread

    async def counted(func, /, *args, **kwargs):
        global _in_flight
        _in_flight += 1
        try:
            return await real_to_thread(func, *args, **kwargs)
        finally:
            _in_flight -= 1

    monkeypatch.setattr(asyncio, "to_thread", counted)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self._sleepers: list[tuple[float, asyncio.Future]] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        future = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.now + seconds, future))
        await future

    async def advance(self, seconds: float) -> None:
        self.now += seconds
        for deadline, future in self._sleepers:
            if deadline <= self.now and not future.done():
                future.set_result(None)
        await settle()


async def settle() -> None:
    """Deixa o loop rodar até as tasks prontas esgotarem os `await` que não dependem do relógio.

    Uma task parada em `asyncio.to_thread` não avança com giros do loop: a thread volta quando o SO a agenda (em 2 CPUs,
    bem depois de 30 giros). Sem esperar por ela, o teste seguiria antes de a task chegar ao próximo `await` do relógio
    (o `advance` acordaria um `sleep` que ainda não existe) e travaria. Por isso o `settle` só termina com nenhuma
    thread em voo depois dos giros.
    """
    deadline = time.monotonic() + SETTLE_DEADLINE_SECONDS
    while True:
        for _ in range(SETTLE_SPINS):
            await asyncio.sleep(0)
        if not _in_flight:
            return
        while _in_flight:
            if time.monotonic() > deadline:
                raise TimeoutError(f"settle: {_in_flight} chamada(s) de to_thread sem voltar em {SETTLE_DEADLINE_SECONDS}s")
            await asyncio.sleep(0.001)
