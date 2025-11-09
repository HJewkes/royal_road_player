"""Event manager for broadcasting queue status updates via Server-Sent Events (SSE)."""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class QueueEventManager:
    """Manages SSE connections and broadcasts queue status updates."""
    
    def __init__(self):
        """Initialize event manager."""
        self._connections: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
    
    async def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to queue events. Returns a queue that will receive event messages.
        
        Returns:
            Queue that will receive event dicts with 'event' and 'data' keys
        """
        async with self._lock:
            queue = asyncio.Queue()
            self._connections.add(queue)
            logger.debug(f"New SSE subscriber connected. Total subscribers: {len(self._connections)}")
            return queue
    
    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from queue events."""
        async with self._lock:
            self._connections.discard(queue)
            logger.debug(f"SSE subscriber disconnected. Total subscribers: {len(self._connections)}")
    
    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcast an event to all connected clients.
        
        Args:
            event_type: Event type (e.g., 'status', 'job_complete', 'job_started')
            data: Event data dictionary (will be JSON serialized)
        """
        message = {
            'event': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        async with self._lock:
            if not self._connections:
                return  # No subscribers
            
            # Remove disconnected queues
            disconnected = set()
            for queue in self._connections:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    # Queue is full, client is slow - disconnect them
                    logger.warning("SSE queue full, disconnecting slow client")
                    disconnected.add(queue)
                except Exception as e:
                    logger.error(f"Error sending SSE message: {e}")
                    disconnected.add(queue)
            
            # Clean up disconnected queues
            for queue in disconnected:
                self._connections.discard(queue)
    
    async def broadcast_status_update(self, status: Dict[str, Any]) -> None:
        """Broadcast a queue status update."""
        await self.broadcast('status', status)
    
    async def broadcast_job_started(self, job: Dict[str, Any]) -> None:
        """Broadcast that a job started processing."""
        await self.broadcast('job_started', job)
    
    async def broadcast_job_completed(self, job: Dict[str, Any]) -> None:
        """Broadcast that a job completed."""
        await self.broadcast('job_completed', job)
    
    async def broadcast_job_failed(self, job: Dict[str, Any]) -> None:
        """Broadcast that a job failed."""
        await self.broadcast('job_failed', job)
    
    def get_subscriber_count(self) -> int:
        """Get current number of connected subscribers."""
        return len(self._connections)


# Global event manager instance
_event_manager: Optional[QueueEventManager] = None


def get_event_manager() -> QueueEventManager:
    """Get the global queue event manager instance."""
    global _event_manager
    if _event_manager is None:
        _event_manager = QueueEventManager()
    return _event_manager

