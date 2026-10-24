"""
Leituras de histórico da Evolution que o `evolution_client` não tinha: grupos e Messages paginadas. Mixin do
`EvolutionAPIService`, em módulo à parte para o cliente não crescer. A importação (`history_sync`) chama só os métodos
públicos do `evolution_api` (`fetch_chats`, `fetch_contacts`, `fetch_groups`, `fetch_messages_page`), nunca o transporte.
"""
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()

# A Evolution devolve até `offset` Messages por página, da mais nova para a mais antiga.
MESSAGES_PAGE_SIZE = 500
# Leituras do histórico são pesadas (milhares de linhas): prazo maior que o das chamadas comuns.
HISTORY_TIMEOUT = 60.0


def as_list(result: Any) -> List[Dict[str, Any]]:
    """Versões da Evolution devolvem a lista pura ou embrulhada em `data`/`records`/`groups`."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("data", "records", "groups"):
            if isinstance(result.get(key), list):
                return result[key]
    return []


class HistoryReads:
    """Leituras de histórico; exige `_request` (vem do `EvolutionAPIService`)."""

    async def fetch_groups(self, instance_name: str) -> List[Dict[str, Any]]:
        """`GET /group/fetchAllGroups/{instance}`: `id` (`...@g.us`) e `subject`, sem participantes."""
        logger.info("Fetching groups from Evolution API", instance=instance_name)
        result = await self._request(
            "GET",
            f"/group/fetchAllGroups/{instance_name}",
            params={"getParticipants": "false"},
            timeout=HISTORY_TIMEOUT,
        )
        return as_list(result)

    async def fetch_messages_page(self, instance_name: str, page: int) -> tuple[List[Dict[str, Any]], int]:
        """Uma página de `POST /chat/findMessages/{instance}` e o total de páginas."""
        result = await self._request(
            "POST",
            f"/chat/findMessages/{instance_name}",
            data={"page": page, "offset": MESSAGES_PAGE_SIZE},
            timeout=HISTORY_TIMEOUT,
        )
        block = result.get("messages") if isinstance(result, dict) else result
        if isinstance(block, dict):
            pages = block.get("pages")
            return as_list(block), pages if isinstance(pages, int) else 1
        return as_list(block), 1
