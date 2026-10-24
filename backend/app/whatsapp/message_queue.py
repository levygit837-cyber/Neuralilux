"""RabbitMQ via aio-pika: publicação do webhook e consumo concorrente da fila.

Tudo roda no event loop de quem chama. O worker mantém um único loop persistente e entrega até
`RABBITMQ_PREFETCH` mensagens em paralelo; a ordem dentro de uma Conversation é garantida pelo
consumer (lock por `conversation_id`), não por esta camada.

Há uma única fila, `webhooks.evolution`, com dead-letter: o que o consumer rejeita, o que vence o TTL e o que
sai pela cabeça por causa do `x-max-length` vai para `webhooks.evolution.dlq` (pela exchange
`webhooks.evolution.dlx`) em vez de sumir. Inspeção e reprocesso da DLQ, e a migração de uma fila criada antes
dela: `docs/operations.md`.
"""
import asyncio
import base64
import json
from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Optional

import aio_pika
import structlog
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustChannel,
    AbstractRobustConnection,
)
from aiormq.exceptions import ChannelPreconditionFailed

from app.core.config import settings

logger = structlog.get_logger()

QUEUE_TTL_MS = 86400000
QUEUE_MAX_LENGTH = 100000


@dataclass(frozen=True)
class WebhookQueue:
    """Topologia da fila de webhook: a fila, a exchange de dead-letter e a DLQ, com os limites de cada uma."""

    name: str
    ttl_ms: int = QUEUE_TTL_MS
    max_length: int = QUEUE_MAX_LENGTH

    @property
    def dlx(self) -> str:
        return f"{self.name}.dlx"

    @property
    def dlq(self) -> str:
        return f"{self.name}.dlq"

    @property
    def arguments(self) -> Dict[str, Any]:
        """Argumentos da fila. Têm de ser idênticos aos de uma fila já existente, senão o broker recusa a
        declaração (`PRECONDITION_FAILED`): uma fila criada antes da DLQ passa por `queue_admin.migrate`.

        `drop-head` no overflow: a mensagem mais antiga sai para a DLQ e a nova entra, então o publish nunca falha
        por fila cheia. `reject-publish-dlx` faria o broker recusar a nova (o webhook responderia 503 e a Evolution
        reenviaria uma mensagem que já está na DLQ). Com o ack logo depois de gravar (#91), a fila só enche com o
        worker parado ou travado, e as mais antigas são as que o consumer já não responderia (`SKIP_STALE`).
        """
        return {
            "x-message-ttl": self.ttl_ms,
            "x-max-length": self.max_length,
            "x-overflow": "drop-head",
            "x-dead-letter-exchange": self.dlx,
            "x-dead-letter-routing-key": self.name,
        }

    @property
    def legacy_arguments(self) -> Dict[str, Any]:
        """Argumentos da fila antes da DLQ (só TTL e tamanho): o que `queue_admin.rollback` recria para o código antigo."""
        return {"x-message-ttl": self.ttl_ms, "x-max-length": self.max_length}

    @property
    def dlq_arguments(self) -> Dict[str, Any]:
        # Teto para a DLQ não crescer sem fim; passando dele, as mais antigas somem (alerte pela profundidade).
        return {"x-max-length": self.max_length}

    async def declare_dead_letter(self, channel: AbstractChannel) -> AbstractQueue:
        """Declara a DLX e a DLQ, ligada à DLX pelo nome da fila. Não toca na fila principal."""
        dlx = await channel.declare_exchange(self.dlx, aio_pika.ExchangeType.DIRECT, durable=True)
        dlq = await channel.declare_queue(self.dlq, durable=True, arguments=self.dlq_arguments)
        await dlq.bind(dlx, routing_key=self.name)
        return dlq

    async def declare(self, channel: AbstractChannel) -> AbstractQueue:
        """Declara a topologia inteira e devolve a fila principal."""
        await self.declare_dead_letter(channel)
        return await channel.declare_queue(self.name, durable=True, arguments=self.arguments)


WEBHOOKS = WebhookQueue("webhooks.evolution")

Consumer = Callable[[Dict[str, Any]], Awaitable[Any]]


def json_safe(value: Any) -> Any:
    """Converte `bytes` (ex.: anexo binário do websocket da Evolution) em base64, recursivamente.

    É a única conversão do caminho do webhook: o corpo HTTP já é JSON e não traz `bytes`.
    """
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("utf-8")
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def _whatsapp_id(event_data: Dict[str, Any]) -> Optional[str]:
    """`data.key.id` do evento (o id da Message no WhatsApp); None em eventos sem `key` (ex.: `connection.update`)."""
    data = event_data.get("data")
    key = data.get("key") if isinstance(data, dict) else None
    value = key.get("id") if isinstance(key, dict) else None
    return value if isinstance(value, str) and value else None


class MessageQueueService:
    """Conexão, publicação e consumo da fila de webhooks do pipeline WhatsApp."""

    def __init__(self, topology: WebhookQueue = WEBHOOKS) -> None:
        self._topology = topology
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None
        self._queue: Optional[AbstractQueue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._open_lock: Optional[asyncio.Lock] = None
        self._consumer: Optional[Consumer] = None
        self._consumer_tag: Optional[str] = None
        self._in_flight: set[asyncio.Task] = set()
        self._stopped: Optional[asyncio.Event] = None

    async def connect(self) -> bool:
        """Abre a conexão; falha só vai para o log (o publish tenta de novo)."""
        try:
            await self._open()
            # Sem a URL no log: ela carrega a senha do broker.
            logger.info("Connected to RabbitMQ", prefetch=settings.RABBITMQ_PREFETCH)
            return True
        except Exception:
            logger.exception("Failed to connect to RabbitMQ")
            return False

    async def _open(self) -> None:
        """Garante canal aberto no event loop atual; uma conexão de outro loop é descartada."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._connection, self._channel, self._queue = loop, None, None, None
            self._open_lock = asyncio.Lock()
        assert self._open_lock is not None
        async with self._open_lock:
            if self._channel is not None and not self._channel.is_closed:
                return
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            try:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH)
                queue = await self._topology.declare(channel)
            except BaseException as e:
                # Sem fechar, cada tentativa falha deixaria uma conexão aberta no broker.
                await connection.close()
                if isinstance(e, ChannelPreconditionFailed):
                    logger.exception(
                        "Queue exists with other arguments: migrate it (docs/operations.md)",
                        queue=self._topology.name,
                    )
                raise
            self._connection, self._channel, self._queue = connection, channel, queue

    async def disconnect(self) -> None:
        """Fecha a conexão."""
        try:
            if self._connection is not None and not self._connection.is_closed:
                await self._connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception:
            logger.exception("Error disconnecting from RabbitMQ")
        finally:
            self._connection, self._channel, self._queue, self._loop = None, None, None, None

    async def publish_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Publica um evento da Evolution (webhook ou websocket) como mensagem persistente.

        Devolve False (e loga) se não conseguir; o webhook responde 503 para a Evolution reenviar.
        """
        queue = self._topology.name
        try:
            await self._open()
            assert self._channel is not None
            message = {"type": "webhook_event", "event": event_data.get("event"), "data": event_data}
            whatsapp_id = _whatsapp_id(event_data)
            await self._channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(json_safe(message), default=str).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    # Id do WhatsApp (`key.id`): aparece no log da DLQ e no `peek`, para achar a mensagem.
                    message_id=whatsapp_id,
                ),
                routing_key=queue,
            )
            logger.info("Message published", queue=queue)
            return True
        except Exception:
            logger.exception("Failed to publish", queue=queue)
            return False

    def register_consumer(self, callback: Consumer) -> None:
        """Registra o callback assíncrono da fila."""
        self._consumer = callback
        logger.info("Consumer registered", queue=self._topology.name)

    async def _on_message(self, callback: Consumer, message: AbstractIncomingMessage) -> None:
        """Entrega uma mensagem ao callback e a resolve no broker.

        Rejeitar sem requeue (`reject`/`nack(requeue=False)`) manda a mensagem para a DLQ pela DLX da fila.
        "Falha repetida" é a segunda falha: JSON inválido não tem conserto e vai direto; erro do callback devolve
        a mensagem à fila uma única vez e, se ela já foi reentregue (`redelivered`), vai para a DLQ, senão uma
        mensagem venenosa giraria em loop quente. `redelivered` basta numa fila clássica; `x-delivery-count`
        exigiria fila quorum, outra migração, sem ganho aqui (o consumer é idempotente por Message id).
        """
        task = asyncio.current_task()
        if task is not None:
            self._in_flight.add(task)
        try:
            try:
                payload = json.loads(message.body)
            except ValueError:
                logger.exception("Invalid JSON, sent to the dead-letter queue", dlq=self._topology.dlq)
                await message.reject(requeue=False)
                return
            try:
                await callback(payload)
            except Exception:
                requeue = not message.redelivered
                if requeue:
                    logger.exception("Processing error, requeueing once", queue=message.routing_key)
                else:
                    logger.exception(
                        "Processing error on redelivery, sent to the dead-letter queue",
                        queue=message.routing_key,
                        dlq=self._topology.dlq,
                        message_id=message.message_id,
                    )
                await message.nack(requeue=requeue)
                return
            await message.ack()
        finally:
            if task is not None:
                self._in_flight.discard(task)

    async def start_consuming(self) -> None:
        """Consome a fila até `stop_consuming()`."""
        if self._consumer is None:
            raise RuntimeError("No consumer registered")
        await self._open()
        assert self._queue is not None
        self._stopped = asyncio.Event()
        callback = self._consumer
        self._consumer_tag = await self._queue.consume(partial(self._on_message, callback))
        logger.info("Started consuming", queue=self._topology.name, prefetch=settings.RABBITMQ_PREFETCH)
        await self._stopped.wait()

    async def stop_consuming(self) -> None:
        """Para de receber e espera as entregas em andamento terminarem."""
        if self._queue is not None and self._consumer_tag is not None:
            try:
                await self._queue.cancel(self._consumer_tag)
            except Exception:
                logger.exception("Failed to cancel consumer", queue=self._topology.name)
        self._consumer_tag = None
        if self._in_flight:
            await asyncio.gather(*tuple(self._in_flight), return_exceptions=True)
        if self._stopped is not None:
            self._stopped.set()


message_queue_service = MessageQueueService()
