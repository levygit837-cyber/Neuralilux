"""Relógio virtual dos testes de agrupamento: `sleep` só acorda quando o teste avança o tempo."""
import asyncio


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
    """Deixa o loop rodar até as tasks prontas esgotarem os `await` que não dependem do relógio."""
    for _ in range(30):
        await asyncio.sleep(0)
