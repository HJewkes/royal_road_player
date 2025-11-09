"""Job status enumeration for the job queue."""

from enum import Enum


class JobStatus(str, Enum):
    """Status of a job in the queue."""
    
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

