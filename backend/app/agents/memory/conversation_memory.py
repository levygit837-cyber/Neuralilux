"""
Conversation Memory - Gerenciamento de contexto e memória por conversa.
Usa Redis para cache rápido e DB para persistência de longo prazo.
"""
from typing import Optional, Dict, Any, List
import json
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ConversationMemory:
    """
    Gerencia a memória de uma conversa específica.
    Armazena contexto atual (carrinho, preferências, dados coletados)
    em Redis para acesso rápido.
    """

    # Prefixo das chaves no Redis
    KEY_PREFIX = "agent:memory:"

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.redis_key = f"{self.KEY_PREFIX}{conversation_id}"
        self._cache: Dict[str, Any] = {}
        self._loaded = False

    async def load(self) -> Dict[str, Any]:
        """Carrega a memória do Redis."""
        if self._loaded:
            return self._cache

        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            data = r.get(self.redis_key)
            if data:
                self._cache = json.loads(data)
            self._loaded = True
            return self._cache
        except Exception as e:
            logger.warning("Failed to load memory from Redis", error=str(e))
            self._loaded = True
            return self._cache

    async def save(self) -> None:
        """Salva a memória atual no Redis."""
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            r.setex(
                self.redis_key,
                3600 * 24,  # TTL: 24 horas
                json.dumps(self._cache, default=str)
            )
        except Exception as e:
            logger.warning("Failed to save memory to Redis", error=str(e))

    async def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor da memória."""
        await self.load()
        return self._cache.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        """Define um valor na memória."""
        await self.load()
        self._cache[key] = value
        await self.save()

    async def get_pedido(self) -> List[Dict[str, Any]]:
        """Obtém o pedido atual da conversa."""
        return await self.get("pedido_atual", [])

    async def set_pedido(self, pedido: List[Dict[str, Any]]) -> None:
        """Salva o pedido atual da conversa."""
        await self.set("pedido_atual", pedido)

    async def get_cliente_info(self) -> Dict[str, Any]:
        """Obtém as informações coletadas do cliente."""
        return await self.get("cliente_info", {})

    async def set_cliente_info(self, info: Dict[str, Any]) -> None:
        """Salva as informações do cliente."""
        await self.set("cliente_info", info)

    async def get_context(self) -> Dict[str, Any]:
        """Obtém todo o contexto da conversa."""
        await self.load()
        return self._cache.copy()

    async def clear(self) -> None:
        """Limpa toda a memória da conversa."""
        self._cache = {}
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            r.delete(self.redis_key)
        except Exception as e:
            logger.warning("Failed to clear memory from Redis", error=str(e))

    async def append_message_summary(self, role: str, content: str) -> None:
        """Adiciona um resumo da mensagem ao histórico de contexto."""
        summaries = await self.get("message_summaries", [])
        summaries.append({
            "role": role,
            "content": content[:200],  # Limitar tamanho
        })
        # Manter apenas os últimos 10 resumos
        if len(summaries) > 10:
            summaries = summaries[-10:]
        await self.set("message_summaries", summaries)