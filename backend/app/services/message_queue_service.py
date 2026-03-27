"""
Message Queue Service - RabbitMQ integration for async message processing
"""
import json
import pika
import asyncio
import structlog
from typing import Callable, Dict, Any, Optional
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings

logger = structlog.get_logger()


class MessageQueueService:
    """Service for RabbitMQ message queue operations"""
    
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._consumers: Dict[str, Callable] = {}
        self._is_consuming = False
        
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            parameters = pika.URLParameters(settings.RABBITMQ_URL)
            parameters.heartbeat = 600
            parameters.blocked_connection_timeout = 300
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self._declare_queues()
            logger.info("Connected to RabbitMQ", url=settings.RABBITMQ_URL)
            return True
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ", error=str(e))
            return False
    
    def _declare_queues(self):
        """Declare all required queues"""
        queues = [
            "whatsapp.messages.incoming",
            "whatsapp.messages.outgoing",
            "whatsapp.messages.processed",
            "whatsapp.messages.send",
            "webhooks.evolution",
            "ai.processing",
            "notifications",
        ]
        for queue in queues:
            self.channel.queue_declare(
                queue=queue,
                durable=True,
                arguments={'x-message-ttl': 86400000, 'x-max-length': 100000}
            )
    
    def disconnect(self):
        """Close RabbitMQ connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error("Error disconnecting from RabbitMQ", error=str(e))
    
    def publish(self, queue: str, message: Dict[str, Any], priority: int = 0, headers: Optional[Dict] = None) -> bool:
        """Publish a message to a queue"""
        try:
            if not self.channel or self.channel.is_closed:
                self.connect()
            properties = pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                priority=priority,
                headers=headers or {}
            )
            self.channel.basic_publish(
                exchange='', routing_key=queue, body=json.dumps(message), properties=properties
            )
            logger.info("Message published", queue=queue)
            return True
        except Exception as e:
            logger.error("Failed to publish", queue=queue, error=str(e))
            return False
    
    def publish_whatsapp_message(self, message_data: Dict[str, Any]) -> bool:
        """Publish an incoming WhatsApp message"""
        return self.publish(
            queue="whatsapp.messages.incoming",
            message={"type": "whatsapp_message", "data": message_data},
            priority=5
        )
    
    def publish_outgoing_message(self, message_data: Dict[str, Any]) -> bool:
        """Publish an outgoing WhatsApp message"""
        return self.publish(
            queue="whatsapp.messages.send",
            message={"type": "send_message", "data": message_data},
            priority=7
        )
    
    def publish_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Publish a webhook event"""
        return self.publish(
            queue="webhooks.evolution",
            message={"type": "webhook_event", "event": event_data.get("event"), "data": event_data}
        )
    
    def publish_ai_processing(self, processing_data: Dict[str, Any]) -> bool:
        """Publish for AI processing"""
        return self.publish(
            queue="ai.processing",
            message={"type": "ai_process", "data": processing_data},
            priority=6
        )
    
    def register_consumer(self, queue: str, callback: Callable):
        """Register a consumer callback"""
        self._consumers[queue] = callback
        logger.info("Consumer registered", queue=queue)
    
    def _process_message(self, callback: Callable, ch, method, properties, body):
        """Process a message from queue"""
        try:
            message = json.loads(body)
            logger.info("Processing", queue=method.routing_key)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(callback(message))
                ch.basic_ack(delivery_tag=method.delivery_tag)
            finally:
                loop.close()
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON", error=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error("Processing error", error=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages"""
        if not self.channel or self.channel.is_closed:
            self.connect()
        for queue, callback in self._consumers.items():
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=queue, on_message_callback=partial(self._process_message, callback))
            logger.info("Started consuming", queue=queue)
        self._is_consuming = True
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
        finally:
            self.disconnect()
    
    def stop_consuming(self):
        """Stop consuming messages"""
        if self.channel and self._is_consuming:
            self.channel.stop_consuming()
            self._is_consuming = False
    
    def get_queue_stats(self, queue: str) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            if not self.channel or self.channel.is_closed:
                self.connect()
            result = self.channel.queue_declare(queue=queue, durable=True, passive=True)
            return {"queue": queue, "message_count": result.method.message_count, "consumer_count": result.method.consumer_count}
        except Exception as e:
            return {"queue": queue, "error": str(e)}
    
    def purge_queue(self, queue: str) -> bool:
        """Purge all messages from queue"""
        try:
            if not self.channel or self.channel.is_closed:
                self.connect()
            self.channel.queue_purge(queue)
            return True
        except Exception as e:
            return False


message_queue_service = MessageQueueService()