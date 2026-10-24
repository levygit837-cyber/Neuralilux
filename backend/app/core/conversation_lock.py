"""Exclusão por Conversation entre processos (#92): nunca dois Turns, nem dois refreshes de Summary, ao mesmo tempo.

O claim por Message (`whatsapp/turn_state.py`) garante que a MESMA Message é respondida uma vez. Ele não impede dois
Turns de Messages DIFERENTES da mesma Conversation (uma rajada dividida entre réplicas do worker) de rodarem juntos, sem
um ver a resposta do outro. Este lock cobre esse caso. A chave leva o tipo, e cada tipo é um lock independente:

- `TURN`: o Turn inteiro (claim, Gateway, envio, fechamento da Message). Chave: id da Conversation.
- `SUMMARY`: o refresh do Summary. Separado do Turn de propósito: o Turn lê o Summary de uma vez e o Contact não pode
  esperar o Gateway do resumo. Chave: id da Conversation.
- `SAVE`: gravar uma Message do webhook (Session, não lidas, dedup e eco) e enviar uma resposta. É o que impede o eco
  de uma resposta de ser lido antes de a réplica que a enviou gravá-la. Chave: Instance + JID (`jid_scope`), porque a
  Conversation pode ainda não existir.

**Postgres.** Advisory lock de SESSÃO (`pg_try_advisory_lock`), segurado numa conexão enquanto o bloco roda. Não é lock
transacional porque o Turn faz vários commits e fala com o Gateway por até `TURN_TIMEOUT_SECONDS`: uma transação aberta
esse tempo todo seria pior que uma conexão parada. As conexões vêm de um engine PRÓPRIO (`LOCK_POOL_SIZE`, sem overflow),
nunca do pool dos dados: quem segura um lock precisa de uma conexão de dados para andar, e se os dois dividissem o pool,
locks parados poderiam ocupá-lo inteiro e travar todos. Quem espera NÃO segura conexão: é um laço de tentativas, a
conexão volta ao pool a cada uma, com `POLL_SECONDS` entre elas. Pool de locks esgotado conta como "ocupado" (o
chamador espera ou desiste), nunca bloqueia o event loop. Se o processo morre, o Postgres solta o lock ao fechar a conexão.

**Outros bancos (SQLite dos testes e do dev).** `asyncio.Lock` por chave, só dentro do processo. É a garantia de antes do
#92: com SQLite há um único worker, e o `TurnBatcher` já serializa a Conversation dentro dele.

A chave é um inteiro de 64 bits derivado do tipo e do identificador (`lock_key`), e não `hashtext` (32 bits): uma colisão
só faria duas Conversations esperarem uma pela outra, mas 64 bits a tornam irrelevante.
"""
import asyncio
import hashlib
import weakref
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.core.config import settings

logger = structlog.get_logger()

TURN = "turn"
SUMMARY = "summary"
SAVE = "save"

POLL_SECONDS = 0.2

_TRY = text("SELECT pg_try_advisory_lock(CAST(:key AS bigint))")
_UNLOCK = text("SELECT pg_advisory_unlock(CAST(:key AS bigint))")

# Sem Postgres: chave -> [Lock, quantos o esperam ou seguram]. A entrada some quando ninguém a usa.
_local: dict[int, list] = {}
# Engine dos locks de cada engine de dados (uma entrada por banco, criada na primeira vez que o lock é pedido).
_engines: "weakref.WeakKeyDictionary[Engine, Engine]" = weakref.WeakKeyDictionary()


class LockBusy(Exception):
    """A Conversation continua com outro Turn (ou Summary) depois do tempo de espera."""


def lock_key(kind: str, ident: str) -> int:
    digest = hashlib.blake2b(f"{kind}:{ident}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


def jid_scope(instance_id: str, remote_jid: str) -> str:
    """Identificador do lock `SAVE`: a Conversation ainda pode não existir quando a Message chega."""
    return f"{instance_id}:{remote_jid}"


def dispose_lock_engines() -> None:
    """Fecha as conexões de lock deste processo (testes, shutdown). Quem as segura as perde, e o Postgres solta os locks."""
    for engine in list(_engines.values()):
        engine.dispose()
    _engines.clear()


@asynccontextmanager
async def conversation_lock(bind: Engine, kind: str, ident: str, wait: float = 0.0) -> AsyncIterator[None]:
    """Segura o lock `kind` de `ident` durante o bloco. `bind`: o engine dos dados (`db.get_bind()`).

    `wait`: quanto esperar, em segundos. `0`: uma tentativa só. Passado o prazo, `LockBusy`.
    """
    key = lock_key(kind, ident)
    if bind.dialect.name == "postgresql":
        conn = await _acquire_postgres(_lock_engine(bind), key, wait)
        try:
            yield
        finally:
            _release_postgres(conn, key)
    else:
        entry = await _acquire_local(key, wait)
        try:
            yield
        finally:
            entry[0].release()
            _drop(key, entry)


def _lock_engine(bind: Engine) -> Engine:
    engine = _engines.get(bind)
    if engine is None:
        engine = _engines[bind] = create_engine(
            bind.url, pool_size=settings.LOCK_POOL_SIZE, max_overflow=0, pool_timeout=0, pool_pre_ping=True
        )
    return engine


async def _acquire_postgres(engine: Engine, key: int, wait: float) -> Connection:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    while True:
        conn = _try_lock(engine, key)
        if conn is not None:
            return conn
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise LockBusy
        await asyncio.sleep(min(POLL_SECONDS, remaining))


def _try_lock(engine: Engine, key: int) -> Connection | None:
    try:
        conn = engine.connect()
    except PoolTimeout:
        return None  # todas as conexões de lock estão em uso: igual a um lock ocupado
    try:
        got = bool(conn.execute(_TRY, {"key": key}).scalar())
        conn.commit()  # sem transação aberta enquanto o lock é segurado
    except BaseException:
        conn.invalidate()  # a tentativa pode ter vencido no servidor: fechar a conexão de verdade solta o lock
        conn.close()
        raise
    if got:
        return conn
    conn.close()
    return None


def _release_postgres(conn: Connection, key: int) -> None:
    """Síncrona de propósito: roda no `finally`, inclusive com o Turn cancelado."""
    try:
        unlocked = conn.execute(_UNLOCK, {"key": key}).scalar()
        conn.commit()
        if not unlocked:
            conn.invalidate()  # o lock não era desta conexão: não a devolva ao pool
    except Exception:
        # Conexão quebrada. Fechá-la de verdade solta o lock; devolvê-la ao pool o deixaria preso nela.
        logger.exception("Conversation lock release failed, connection dropped")
        conn.invalidate()
    finally:
        conn.close()


async def _acquire_local(key: int, wait: float) -> list:
    entry = _local.get(key)
    if entry is None:
        entry = _local[key] = [asyncio.Lock(), 0]
    entry[1] += 1
    try:
        if wait <= 0:
            if entry[0].locked():
                raise LockBusy
            await entry[0].acquire()  # livre: volta sem ceder o loop, então ninguém passa na frente
        else:
            try:
                await asyncio.wait_for(entry[0].acquire(), wait)
            except TimeoutError:
                raise LockBusy from None
    except BaseException:
        _drop(key, entry)
        raise
    return entry


def _drop(key: int, entry: list) -> None:
    entry[1] -= 1
    if entry[1] == 0:
        _local.pop(key, None)
