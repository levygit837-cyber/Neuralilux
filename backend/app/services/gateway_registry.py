"""Shim do registry legado; o registry real vive em `app.llm.registry`.

So existe porque `FallbackInferenceService` (legado, removido no T3) ainda chama
`get_assigned_service`. Os Gateways agora falam Messages e nao servem o caminho
OpenAI antigo, entao o legado sempre cai nos provedores padrao.
"""
from app.llm.registry import ensure_default_gateway, invalidate  # noqa: F401


def get_assigned_service(agent_type: str) -> None:
    return None
