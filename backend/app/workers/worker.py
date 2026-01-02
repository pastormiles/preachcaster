"""
RQ Worker Runner
Starts the background worker that processes sermon tasks.

Usage:
    python -m app.workers.worker
    
Or with specific queues:
    python -m app.workers.worker high default low
"""

import sys
import logging

from redis import Redis
from rq import Worker, Queue, Connection

from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def run_worker(queues=None):
    """
    Start the RQ worker.
    
    Args:
        queues: List of queue names to listen on (default: all)
    """
    if queues is None:
        queues = ['high', 'default', 'low']
    
    redis_conn = Redis.from_url(settings.redis_url)
    
    with Connection(redis_conn):
        worker = Worker(
            queues=[Queue(name) for name in queues],
            name='preachcaster-worker'
        )
        
        logger.info(f"Starting worker on queues: {queues}")
        worker.work(with_scheduler=True)


if __name__ == '__main__':
    queues = sys.argv[1:] if len(sys.argv) > 1 else None
    run_worker(queues)
