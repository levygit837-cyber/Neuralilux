"""
Leituras da Evolution usadas pela importação de histórico (`history_sync`): chats, grupos, contatos e
Messages paginadas. Módulo à parte para o `evolution_client` não crescer.
"""
from typing import Any, Dict, List

from app.whatsapp.evolution_client import evolution_api

# A Evolution devolve até `offset` Messages por página, da mais nova para a mais antiga.
MESSAGES_PAGE_SIZE = 500
_TIMEOUT = 60.0


def _as_list(result: Any) -> List[Dict[str, Any]]:
    """Versões da Evolution devolvem a lista pura ou embrulhada em `data`/`records`."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("data", "records", "groups"):
            if isinstance(result.get(key), list):
                return result[key]
    return []


async def find_chats(instance_name: str) -> List[Dict[str, Any]]:
    """`POST /chat/findChats`: um item por chat (1:1, `@lid` e grupo), com `unreadCount`."""
    result = await evolution_api._request("POST", f"/chat/findChats/{instance_name}", data={}, timeout=_TIMEOUT)
    return _as_list(result)


async def find_contacts(instance_name: str) -> List[Dict[str, Any]]:
    """`POST /chat/findContacts`: `remoteJid` e `pushName` dos contatos."""
    result = await evolution_api._request("POST", f"/chat/findContacts/{instance_name}", data={}, timeout=_TIMEOUT)
    return _as_list(result)


async def fetch_all_groups(instance_name: str) -> List[Dict[str, Any]]:
    """`GET /group/fetchAllGroups`: `id` (`...@g.us`) e `subject`, sem participantes."""
    result = await evolution_api._request(
        "GET",
        f"/group/fetchAllGroups/{instance_name}",
        params={"getParticipants": "false"},
        timeout=_TIMEOUT,
    )
    return _as_list(result)


async def find_messages_page(instance_name: str, page: int) -> tuple[List[Dict[str, Any]], int]:
    """Uma página de `POST /chat/findMessages` e o total de páginas."""
    result = await evolution_api._request(
        "POST",
        f"/chat/findMessages/{instance_name}",
        data={"page": page, "offset": MESSAGES_PAGE_SIZE},
        timeout=_TIMEOUT,
    )
    block = result.get("messages") if isinstance(result, dict) else result
    if isinstance(block, dict):
        pages = block.get("pages")
        return _as_list(block), pages if isinstance(pages, int) else 1
    return _as_list(block), 1
