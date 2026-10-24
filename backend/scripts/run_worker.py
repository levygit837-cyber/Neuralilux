"""
WhatsApp Message Queue Worker
Run this script to start consuming messages from RabbitMQ

Um único event loop persistente atende todas as mensagens (até RABBITMQ_PREFETCH em paralelo).
No SIGTERM/SIGINT o consumer para de consumir, espera os Turns em voo até SHUTDOWN_TIMEOUT_SECONDS e cancela o resto:
as Messages desses Turns continuam `pending` e a recuperação do próximo worker as retoma.
"""
import sys
import signal
import asyncio
import structlog
from pathlib import Path

# Add backend project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import http_clients
from app.core.config import settings
from app.services.handoff_service import sweep_forever
from app.whatsapp import reimport_guard
from app.whatsapp.consumer import whatsapp_consumer
from app.whatsapp.message_queue import message_queue_service

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
    sweeping = asyncio.create_task(sweep_forever(settings.HANDOFF_SWEEP_INTERVAL_SECONDS))
    waiting = asyncio.create_task(stopping.wait())
    try:
        await asyncio.wait({consuming, waiting}, return_when=asyncio.FIRST_COMPLETED)
        if consuming.done() and not consuming.cancelled() and consuming.exception():
            logger.error("Worker error", exc_info=consuming.exception())
            return 1
        return 0
    finally:
        await whatsapp_consumer.stop()  # espera os Turns e os Summaries até SHUTDOWN_TIMEOUT_SECONDS
        sweeping.cancel()
        await asyncio.gather(consuming, sweeping, return_exceptions=True)
        waiting.cancel()
        await message_queue_service.disconnect()
        await http_clients.close_all()  # Evolution e Gateways: um cliente por destino, vivo até aqui
        await reimport_guard.close()
        logger.info("Worker stopped")


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
