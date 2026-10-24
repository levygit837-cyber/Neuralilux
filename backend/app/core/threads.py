"""`asyncio.to_thread` para trabalho que usa uma Session: a thread não é cancelável, então o cancelamento espera por ela."""
import asyncio
from collections.abc import Callable
from typing import Any


async def settle(task: "asyncio.Future[Any]") -> BaseException | None:
    """Espera a tarefa acabar mesmo sob novos cancelamentos e devolve a exceção dela (ou None). Marca-a como lida."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue  # a thread segue usando a Session: continua esperando
        except Exception:
            break
    return None if task.cancelled() else task.exception()


async def in_thread(fn: Callable[..., Any], *args: Any) -> Any:
    """Roda `fn(*args)` em thread. Se o chamador é cancelado, espera a thread terminar antes de propagar o cancelamento:
    quem fecha a Session depois (o `db.close()` do Turn ou da rota) não pode cruzar com a thread que ainda a usa."""
    task = asyncio.ensure_future(asyncio.to_thread(fn, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await settle(task)
        raise
