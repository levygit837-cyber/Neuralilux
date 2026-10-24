"""
Importação do histórico que a Evolution guarda (chats, grupos e Messages) para o banco.

O webhook só entrega o que chega depois da conexão; esta importação traz o resto. Ela só grava: nunca chama o
Agent, não rola Session, não toca no Handoff e não publica evento por Message. Pode rodar quantas vezes for
preciso: Message já gravada (pelo `message_id`) fica como está.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

import structlog
from sqlalchemy import text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Conversation, Instance, Message
from app.whatsapp.evolution_client import EvolutionAPIError, evolution_api
from app.whatsapp.evolution_history import as_list
from app.whatsapp.message_store import get_or_create_contact, get_or_create_conversation, new_message
from app.whatsapp.webhook_parser import (
    is_group_chat,
    is_ignored_chat,
    is_invisible_message,
    parse_content,
    parse_message_timestamp,
    resolve_remote_jid,
)

logger = structlog.get_logger()

# Quantas Messages novas entram por commit.
COMMIT_EVERY = 200
# Quantas vezes um lote é refeito quando outro processo grava o mesmo `message_id` no meio.
BATCH_ATTEMPTS = 3
# Tamanho do `IN (...)` na checagem de duplicadas.
_DEDUP_CHUNK = 500


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _best_effort(label: str, call) -> List[Dict[str, Any]]:
    """Grupos e contatos só dão nomes: se a Evolution falhar neles, a importação segue com o que tem."""
    try:
        return await call
    except EvolutionAPIError as error:
        logger.warning("History sync: optional Evolution call failed", call=label, error=error.message)
        return []


async def _iter_pages(instance_name: str) -> AsyncIterator[List[Dict[str, Any]]]:
    """As páginas de `findMessages`, da mais nova para a mais antiga, uma por vez: nenhuma fica retida aqui."""
    page, pages = 1, 1
    while page <= pages:
        batch, pages = await evolution_api.fetch_messages_page(instance_name, page)
        yield batch
        page += 1


def _lid_aliases(records: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """`@lid` -> número real, aprendido de qualquer Message do mesmo chat que traga o par."""
    aliases: Dict[str, str] = {}
    for record in records:
        key = record.get("key") or {}
        lid = key.get("remoteJid") or ""
        if lid.endswith("@lid"):
            resolved = resolve_remote_jid(key, record)
            if resolved != lid:
                aliases[lid] = resolved
    return aliases


def _record_push_names(records: List[Dict[str, Any]], first_seq: int, push_names: Dict[str, tuple[int, str]]) -> int:
    """Guarda o pushName mais recente por JID (ainda sem resolver `@lid`) e devolve o próximo número de ordem.

    O pushName de uma Message `fromMe` é o do nosso número e o de uma Message de grupo é o do participante:
    nenhum dos dois nomeia o chat. O número de ordem (0 = a Message mais nova do histórico) deixa
    `_collect_names` escolher a mais recente depois que todos os pares `@lid` forem conhecidos.
    """
    for offset, record in enumerate(records):
        key = record.get("key") or {}
        jid = resolve_remote_jid(key, record)
        if key.get("fromMe") or is_group_chat(jid) or not record.get("pushName"):
            continue
        push_names.setdefault(jid, (first_seq + offset, record["pushName"]))
    return first_seq + len(records)


async def _scan_history(instance_name: str) -> tuple[Dict[str, str], Dict[str, tuple[int, str]]]:
    """Primeira passada: os pares `@lid` -> número e os pushNames de todo o histórico, descartando as páginas.

    Um `@lid` só se resolve com um par que pode estar em qualquer página (inclusive numa mais nova que a
    Message), então a escrita precisa do mapa completo antes de começar. O mapa é pequeno; as Messages não.
    """
    aliases: Dict[str, str] = {}
    push_names: Dict[str, tuple[int, str]] = {}
    seq = 0
    async for records in _iter_pages(instance_name):
        aliases.update(_lid_aliases(records))
        seq = _record_push_names(records, seq, push_names)
    return aliases, push_names


def _collect_names(
    push_names: Dict[str, tuple[int, str]],
    chats: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    contacts: List[Dict[str, Any]],
    resolve,
) -> Dict[str, str]:
    """Nome de exibição por JID. Prioridade: assunto do grupo; pushName de Message recebida; findContacts; findChats."""
    names: Dict[str, str] = {}
    for group in groups:
        if group.get("id") and group.get("subject"):
            names[group["id"]] = group["subject"]
    for jid, (_, push_name) in sorted(push_names.items(), key=lambda item: item[1][0]):  # do mais novo: vale o mais recente
        names.setdefault(resolve(jid), push_name)
    for source, jid_field in ((contacts, "remoteJid"), (chats, "remoteJid")):
        for item in source:
            jid = resolve(item.get(jid_field) or item.get("id") or "")
            if jid and item.get("pushName"):
                names.setdefault(jid, item["pushName"])
    return names


def _existing_message_ids(db: Session, ids: List[str]) -> set[str]:
    found: set[str] = set()
    for start in range(0, len(ids), _DEDUP_CHUNK):
        chunk = ids[start : start + _DEDUP_CHUNK]
        found.update(row[0] for row in db.query(Message.message_id).filter(Message.message_id.in_(chunk)))
    return found


def _apply_unread(db: Session, created: Dict[str, str], chats: List[Dict[str, Any]], resolve) -> None:
    """`unreadCount` do findChats vira o contador, só das Conversations criadas nesta importação.

    As que já existiam têm contador próprio (zerado por `/read`, somado pelo webhook): reaplicar o da Evolution
    a cada importação desfaria os dois. `created` mapeia o JID para o id da Conversation criada, então não há
    leitura nenhuma: um único UPDATE em lote pela chave primária. null: deixa como está.
    """
    unread_by_id: Dict[str, int] = {}
    for chat in chats:
        unread = chat.get("unreadCount")
        if not isinstance(unread, int) or isinstance(unread, bool):
            continue
        conversation_id = created.get(resolve(chat.get("remoteJid") or chat.get("id") or ""))
        if conversation_id:
            unread_by_id[conversation_id] = max(unread, 0)
    if unread_by_id:
        db.execute(update(Conversation), [{"id": cid, "unread_count": n} for cid, n in unread_by_id.items()])


def _write_batch(
    db: Session,
    instance: Instance,
    batch: List[tuple],
    names: Dict[str, str],
    cache: Dict[str, Conversation],
) -> tuple[Dict[str, Conversation], Dict[str, str], int]:
    """Adiciona as Messages do lote à sessão, sem commit. Pode ser refeito do zero depois de um rollback.

    `known` é recalculado a cada tentativa: uma Message que o webhook ou outro processo gravou desde a
    tentativa anterior é vista aqui e pulada. Devolve as Conversations resolvidas no lote, as criadas
    (JID -> id) e quantas Messages entraram. `cache` só tem Conversations de lotes já confirmados.
    """
    known = _existing_message_ids(db, [item[1] for item in batch])
    resolved: Dict[str, Conversation] = {}
    created: Dict[str, str] = {}
    newest: Dict[str, tuple[datetime, str]] = {}  # conversation.id -> (timestamp, prévia) das Messages do lote
    touched: Dict[str, Conversation] = {}
    count = 0

    for timestamp, message_id, jid, record in batch:
        if message_id in known:
            continue
        known.add(message_id)
        from_me = bool((record.get("key") or {}).get("fromMe"))

        conversation = cache.get(jid) or resolved.get(jid)
        if conversation is None:
            contact = get_or_create_contact(db, instance, jid, name=names.get(jid))
            conversation, was_created = get_or_create_conversation(db, instance, contact, jid)
            resolved[jid] = conversation
            if was_created:
                created[jid] = conversation.id

        parsed = parse_content(record.get("message") or {})
        sender_name = record.get("pushName") if is_group_chat(jid) and not from_me else None
        db.add(new_message(instance, conversation, jid, message_id, parsed, from_me, timestamp, sender_name=sender_name))
        count += 1
        touched[conversation.id] = conversation
        if conversation.id not in newest or timestamp >= newest[conversation.id][0]:
            newest[conversation.id] = (timestamp, parsed.content)

    for conversation_id, conversation in touched.items():
        timestamp, content = newest[conversation_id]
        current = _aware(conversation.last_message_at)
        if current is None or timestamp > current:
            conversation.last_message_at = timestamp
            conversation.last_message_preview = content[:200] if content else None
    return resolved, created, count


def _commit_batch(
    db: Session, instance: Instance, instance_id: str, batch: List[tuple], names: Dict[str, str], cache: Dict[str, Conversation]
) -> tuple[Dict[str, Conversation], Dict[str, str], int]:
    """Grava e confirma um lote (transação própria). Em `IntegrityError`, rollback e refaz sem as duplicadas."""
    for attempt in range(1, BATCH_ATTEMPTS + 1):
        try:
            result = _write_batch(db, instance, batch, names, cache)
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            if attempt == BATCH_ATTEMPTS:
                raise
            logger.warning("History sync: concurrent insert, retrying batch", instance_id=instance_id, attempt=attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def _finish_import(db: Session, created_by_jid: Dict[str, str], chats: List[Dict[str, Any]], resolve) -> None:
    _apply_unread(db, created_by_jid, chats, resolve)
    db.commit()


def _candidates(records: List[Dict[str, Any]], resolve) -> List[tuple]:
    """(timestamp, message_id, jid, record) das Messages visíveis da página, a mais antiga primeiro."""
    candidates = []
    for record in records:
        key = record.get("key") or {}
        message_id = key.get("id")
        jid = resolve(resolve_remote_jid(key, record))
        if not message_id or not jid or is_ignored_chat(jid) or is_invisible_message(record.get("message") or {}):
            continue
        candidates.append((parse_message_timestamp(record.get("messageTimestamp")), message_id, jid, record))
    candidates.sort(key=lambda item: item[0])  # a mais antiga primeiro: created_at segue a ordem da conversa
    return candidates


async def _import_history(db: Session, instance: Instance) -> Dict[str, int]:
    """Importa o histórico da Instance e devolve quantas Conversations e Messages foram criadas.

    Duas passadas pelas páginas do `findMessages`, nenhuma delas retém mais de uma página: a primeira só aprende
    os pares `@lid` e os pushNames (`_scan_history`); a segunda grava página a página, e cada lote é uma
    transação. Se outro processo gravar o mesmo `message_id` entre a checagem e o commit (`IntegrityError`),
    o lote sofre rollback e é refeito sem as duplicadas.
    """
    name = instance.evolution_instance_id or instance.name
    chats = as_list(await evolution_api.fetch_chats(name))
    groups = await _best_effort("fetchAllGroups", evolution_api.fetch_groups(name))
    contacts = as_list(await _best_effort("findContacts", evolution_api.fetch_contacts(name)))

    aliases, push_names = await _scan_history(name)

    def resolve(jid: str) -> str:
        """Um `@lid` sem par em nenhuma Message continua como está."""
        return aliases.get(jid, jid)

    names = _collect_names(push_names, chats, groups, contacts, resolve)

    instance_id = instance.id
    cache: Dict[str, Conversation] = {}
    created_by_jid: Dict[str, str] = {}
    messages_created = 0

    async for records in _iter_pages(name):
        candidates = _candidates(records, resolve)
        for start in range(0, len(candidates), COMMIT_EVERY):
            batch = candidates[start : start + COMMIT_EVERY]
            resolved, created, count = await asyncio.to_thread(
                _commit_batch, db, instance, instance_id, batch, names, cache
            )
            cache.update(resolved)
            created_by_jid.update(created)
            messages_created += count

    await asyncio.to_thread(_finish_import, db, created_by_jid, chats, resolve)

    logger.info(
        "History sync finished",
        instance_id=instance_id,
        conversations=len(created_by_jid),
        messages=messages_created,
    )
    return {"conversations": len(created_by_jid), "messages": messages_created}


class SyncAlreadyRunning(Exception):
    """Outra importação da mesma Instance, na API ou no worker, está em andamento."""


def _acquire_lock(bind, key: Dict[str, str]) -> tuple[Connection, bool]:
    """Abre a conexão própria do lock e tenta pegá-lo. Em thread: `connect` e `execute` bloqueiam."""
    conn = bind.connect()
    try:
        acquired = conn.execute(text("SELECT pg_try_advisory_lock(hashtext(:id))"), key).scalar()
        conn.commit()
    except BaseException:
        conn.close()
        raise
    return conn, bool(acquired)


def _release_lock(conn: Connection, key: Dict[str, str], unlock: bool) -> None:
    try:
        if unlock:
            conn.execute(text("SELECT pg_advisory_unlock(hashtext(:id))"), key)
            conn.commit()
    finally:
        conn.close()


async def sync_instance(db: Session, instance: Instance) -> Dict[str, int]:
    """Importa o histórico, uma importação por vez por Instance entre processos (API e worker).

    No Postgres a exclusão é um advisory lock de sessão, segurado numa conexão própria: a `db` devolve a
    conexão ao pool a cada commit, e o lock tem de viver na mesma conexão até o `unlock`. Outras bases
    (os testes em sqlite) não têm o lock. `SyncAlreadyRunning` se o lock já é de outro processo.

    Todo acesso ao banco roda em thread (`asyncio.to_thread`), um de cada vez: a `db` não é compartilhada
    entre threads ao mesmo tempo, só passada de uma para outra, e o event loop segue livre durante a importação.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return await _import_history(db, instance)
    instance_id = instance.id
    key = {"id": instance_id}
    conn, acquired = await asyncio.to_thread(_acquire_lock, bind, key)
    if not acquired:
        await asyncio.to_thread(_release_lock, conn, key, False)
        raise SyncAlreadyRunning(instance_id)
    try:
        return await _import_history(db, instance)
    finally:
        await asyncio.to_thread(_release_lock, conn, key, True)
