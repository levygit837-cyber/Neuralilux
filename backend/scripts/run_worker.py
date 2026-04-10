"""
WhatsApp Message Queue Worker
Run this script to start consuming messages from RabbitMQ
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


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal", signal=signum)
    whatsapp_consumer.stop()
    message_queue_service.disconnect()
    sys.exit(0)


def main():
    """Main entry point for the worker"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting WhatsApp Message Queue Worker")
    
    try:
        # Connect to RabbitMQ
        if not message_queue_service.connect():
            logger.error("Failed to connect to RabbitMQ")
            sys.exit(1)
        
        # Start consuming
        whatsapp_consumer.start()
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error("Worker error", error=str(e))
        sys.exit(1)
    finally:
        whatsapp_consumer.stop()
        message_queue_service.disconnect()
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
