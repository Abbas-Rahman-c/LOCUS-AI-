"""
Worker runner entry point  starts all registered consumer workers.
Each worker polls its own pgmq queue. Workers are co-located here;
business logic stays in the respective modules/.
"""
import asyncio
import logging

from queue.workers.event_worker import run_event_worker

log = logging.getLogger(__name__)


async def start_all_workers() -> None:
    """Launch all queue workers concurrently."""
    log.info("Starting all queue workers...")
    await asyncio.gather(
        run_event_worker(),
        # Add embedding_worker, digest_worker here as they are built
    )


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(start_all_workers())
