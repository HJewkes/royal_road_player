"""Worker entrypoint for background job processing."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.data.database import init_db
from src.services.job_queue import get_queue
from src.utils.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/worker.log'),
    ]
)

logger = logging.getLogger(__name__)
settings = get_settings()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    """Main worker loop."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("Starting Audiobook Worker Service")
    logger.info("=" * 60)
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)
    
    # Start job queue processor
    logger.info("Starting background job processor...")
    queue = get_queue()
    
    try:
        # Start processor with 1 second interval
        processor_task = queue.start_background_processor(interval_seconds=1.0)
        logger.info("✅ Background job processor started")
        logger.info(f"Processing interval: 1.0 seconds")
        logger.info("Worker is running. Press Ctrl+C to stop.")
        
        # Wait for processor task (runs indefinitely)
        await processor_task
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Stop processor
        if queue._processor_task and not queue._processor_task.done():
            queue._processor_task.cancel()
            try:
                await queue._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Worker stopped")


if __name__ == "__main__":
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)
