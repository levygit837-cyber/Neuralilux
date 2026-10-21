"""RabbitMQ via aio-pika: publicação do webhook e consumo concorrente das filas.

Tudo roda no event loop de quem chama. O worker mantém um único loop persistente e entrega até
`RABBITMQ_PREFETCH` mensagens em paralelo; a ordem dentro de uma Conversation é garantida pelo
consumer (lock por `conversation_id`), não por esta camada.
"""
import asyncio
import base64
import json
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Optional

import aio_pika
import structlog
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue, AbstractRobustChannel, AbstractRobustConnection

from app.core.config import settings

logger = structlog.get_logger()

QUEUES = (
    "whatsapp.messages.incoming",
    "whatsapp.messages.outgoing",
    "whatsapp.messages.processed",
    "whatsapp.messages.send",
    "webhooks.evolution",
    "ai.processing",
    "notifications",
)
# Tem de ser idêntico ao declarado nas filas já existentes, senão o broker recusa a declaração.
QUEUE_ARGUMENTS = {"x-message-ttl": 86400000, "x-max-length": 100000}


class MessageQueueService:
    """Conexão, publicação e consumo das filas do pipeline WhatsApp."""

    def __init__(self) -> None:
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None
        self._queues: Dict[str, AbstractQueue] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._open_lock: Optional[asyncio.Lock] = None
        self._consumers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        self._consumer_tags: list[tuple[AbstractQueue, str]] = []
        self._in_flight: set[asyncio.Task] = set()
        self._stopped: Optional[asyncio.Event] = None

    async def connect(self) -> bool:
        """Abre a conexão; falha só vai para o log (o publish tenta de novo)."""
        try:
            await self._open()
            # Sem a URL no log: ela carrega a senha do broker.
            logger.info("Connected to RabbitMQ", prefetch=settings.RABBITMQ_PREFETCH)
            return True
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ", error=str(e))
            return False

    async def _open(self) -> None:
        """Garante canal aberto no event loop atual; uma conexão de outro loop é descartada."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._connection, self._channel, self._queues = loop, None, None, {}
            self._open_lock = asyncio.Lock()
        assert self._open_lock is not None
        async with self._open_lock:
            if self._channel is not None and not self._channel.is_closed:
                return
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH)
            for name in QUEUES:
                self._queues[name] = await self._channel.declare_queue(
                    name, durable=True, arguments=QUEUE_ARGUMENTS
                )

    async def disconnect(self) -> None:
        """Fecha a conexão."""
        try:
            if self._connection is not None and not self._connection.is_closed:
                await self._connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error("Error disconnecting from RabbitMQ", error=str(e))
        finally:
            self._connection, self._channel, self._queues, self._loop = None, None, {}, None

    def _make_json_safe(self, value: Any) -> Any:
        """Recursively convert queue payloads into JSON-safe values."""
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("utf-8")
        if isinstance(value, dict):
            return {key: self._make_json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._make_json_safe(item) for item in value]
        return value

    async def publish(
        self, queue: str, message: Dict[str, Any], priority: int = 0, headers: Optional[Dict] = None
    ) -> bool:
        """Publica uma mensagem persistente na fila. Devolve False (e loga) se não conseguir."""
        try:
            await self._open()
            assert self._channel is not None
            body = json.dumps(self._make_json_safe(message), default=str).encode()
            await self._channel.default_exchange.publish(
                aio_pika.Message(
                    body=body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    priority=priority,
                    headers=headers or {},
                ),
                routing_key=queue,
            )
            logger.info("Message published", queue=queue)
            return True
        except Exception as e:
            logger.error("Failed to publish", queue=queue, error=str(e))
            return False

    async def publish_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Publica um evento do webhook da Evolution."""
        return await self.publish(
            queue="webhooks.evolution",
            message={"type": "webhook_event", "event": event_data.get("event"), "data": event_data},
        )

    def register_consumer(self, queue: str, callback: Callable[[Dict[str, Any]], Awaitable[Any]]) -> None:
        """Registra o callback assíncrono de uma fila."""
        self._consumers[queue] = callback
        logger.info("Consumer registered", queue=queue)

    async def _on_message(
        self, callback: Callable[[Dict[str, Any]], Awaitable[Any]], message: AbstractIncomingMessage
    ) -> None:
        """Entrega uma mensagem ao callback e a resolve no broker.

        JSON inválido é descartado sem requeue. Erro do callback devolve a mensagem à fila uma única vez: se ela já
        foi reentregue (`redelivered`), é descartada, senão uma mensagem venenosa giraria em loop quente.
        """
        task = asyncio.current_task()
        if task is not None:
            self._in_flight.add(task)
        try:
            try:
                payload = json.loads(message.body)
            except ValueError as e:
                logger.error("Invalid JSON", error=str(e))
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
                        "Processing error on redelivery, message dropped",
                        queue=message.routing_key,
                        message_id=message.message_id,
                    )
                await message.nack(requeue=requeue)
                return
            await message.ack()
        finally:
            if task is not None:
                self._in_flight.discard(task)

    async def start_consuming(self) -> None:
        """Consome as filas registradas até `stop_consuming()`."""
        await self._open()
        self._stopped = asyncio.Event()
        for name, callback in self._consumers.items():
            queue = self._queues[name]
            tag = await queue.consume(partial(self._on_message, callback))
            self._consumer_tags.append((queue, tag))
            logger.info("Started consuming", queue=name, prefetch=settings.RABBITMQ_PREFETCH)
        await self._stopped.wait()

    async def stop_consuming(self) -> None:
        """Para de receber e espera as entregas em andamento terminarem."""
        for queue, tag in self._consumer_tags:
            try:
                await queue.cancel(tag)
            except Exception as e:
                logger.error("Failed to cancel consumer", queue=queue.name, error=str(e))
        self._consumer_tags.clear()
        if self._in_flight:
            await asyncio.gather(*tuple(self._in_flight), return_exceptions=True)
        if self._stopped is not None:
            self._stopped.set()


message_queue_service = MessageQueueService()
