"""
WhatsApp Message Queue Worker
Run this script to start consuming messages from RabbitMQ

Um único event loop persistente atende todas as mensagens (até RABBITMQ_PREFETCH em paralelo).
"""
import sys
import signal
import asyncio
import structlog
from pathlib import Path

# Add backend project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.workers.whatsapp_consumer import whatsapp_consumer
from app.services.message_queue_service import message_queue_service

logger = structlog.get_logger()


async def run() -> int:
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()

    def request_stop(signum: int) -> None:
        logger.info("Received shutdown signal", signal=signum)
        stopping.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, request_stop, signum)

    logger.info("Starting WhatsApp Message Queue Worker")
    if not await message_queue_service.connect():
        logger.error("Failed to connect to RabbitMQ")
        return 1

    consuming = asyncio.create_task(whatsapp_consumer.start())
    waiting = asyncio.create_task(stopping.wait())
    try:
        await asyncio.wait({consuming, waiting}, return_when=asyncio.FIRST_COMPLETED)
        if consuming.done() and not consuming.cancelled() and consuming.exception():
            logger.error("Worker error", error=str(consuming.exception()))
            return 1
        return 0
    finally:
        await whatsapp_consumer.stop()  # espera as entregas e os Summaries em andamento
        await asyncio.gather(consuming, return_exceptions=True)
        waiting.cancel()
        await message_queue_service.disconnect()
        logger.info("Worker stopped")


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
