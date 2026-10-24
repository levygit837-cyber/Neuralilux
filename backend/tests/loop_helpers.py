"""Detector de event loop bloqueado: o modo debug do asyncio loga todo callback que segura o loop por mais que
`slow_callback_duration` (logger `asyncio`, "Executing <...> took N seconds")."""
import asyncio
import gc
import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, TypeVar

SLOW_CALLBACK_SECONDS = 0.1
ATTEMPTS = 3

T = TypeVar("T")


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.slow: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith("Executing") and " took " in message:
            self.slow.append(message)


@asynccontextmanager
async def watch_slow_callbacks(threshold: float = SLOW_CALLBACK_SECONDS):
    """Dentro do bloco, o loop corrente roda em modo debug com `slow_callback_duration=threshold`.

    O asyncio só cronometra um callback se o debug já estava ligado quando o passo começou; por isso o bloco cede o
    loop uma vez (`sleep(0)`) logo após ligá-lo, e o código testado roda em passos já cronometrados. Cede de novo ao
    sair: um passo que bloqueou sem nunca suspender só é logado quando termina, e a asserção do teste roda no mesmo passo. O coletor de lixo
    fica desligado no bloco: uma pausa de GC não é chamada bloqueante. O `gc.collect()` de antes do bloco roda num passo
    novo (o `sleep(0)` do início): numa nova tentativa, o passo anterior terminou com o debug ligado e é cronometrado inteiro.

    Devolve a lista (preenchida durante o bloco) dos logs de callback lento; o teste afirma que ela está vazia.
    """
    loop = asyncio.get_running_loop()
    # Sem este `sleep(0)`, numa nova tentativa o `gc.collect()` rodaria no mesmo passo em que a tentativa anterior desligou
    # o debug; esse passo começou com debug ligado, é cronometrado e o `gc.collect()` (100-250 ms) vira "callback lento".
    await asyncio.sleep(0)
    was_debug, was_threshold = loop.get_debug(), loop.slow_callback_duration
    gc.collect()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    collector = _Collector()
    logger = logging.getLogger("asyncio")
    logger.addHandler(collector)
    loop.set_debug(True)
    loop.slow_callback_duration = threshold
    try:
        await asyncio.sleep(0)
        yield collector.slow
        await asyncio.sleep(0)  # o asyncio loga o passo lento só depois que ele termina: cede para o log sair
    finally:
        loop.set_debug(was_debug)
        loop.slow_callback_duration = was_threshold
        if gc_was_enabled:
            gc.enable()
        logger.removeHandler(collector)


async def run_watched(
    action: Callable[[], Awaitable[T]],
    *,
    reset: Callable[[], None] | None = None,
    attempts: int = ATTEMPTS,
) -> tuple[T, list[str]]:
    """Roda `action` sob `watch_slow_callbacks` e devolve `(resultado, logs de callback lento)` da última tentativa.

    Repete até `attempts` vezes e para na primeira tentativa sem log. Um bloqueio de verdade (bcrypt, SQL no loop)
    estoura em toda tentativa; o ruído do host (a suíte roda em vários processos xdist por núcleo, e um passo
    inofensivo pode ser descalonado por centenas de ms) não se repete. `reset` desfaz o efeito de uma tentativa
    antes da próxima.
    """
    for attempt in range(attempts):
        if attempt and reset is not None:
            reset()
        async with watch_slow_callbacks() as slow:
            result = await action()
        if not slow:
            break
    return result, slow
