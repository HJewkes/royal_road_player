"""Chunk job model for the job queue."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.services.job_status import JobStatus


@dataclass
class ChunkJob:
    """Represents a job to process a chunk."""
    
    book_id: str
    chapter_number: int
    chunk_index: int
    speaker: Optional[str] = None
    speed: Optional[float] = None
    status: JobStatus = JobStatus.PENDING
    error: Optional[str] = None
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'book_id': self.book_id,
            'chapter_number': self.chapter_number,
            'chunk_index': self.chunk_index,
            'speaker': self.speaker,
            'speed': self.speed,
            'status': self.status.value,
            'error': self.error,
            'created_at': self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkJob':
        """Create from dictionary."""
        return cls(
            book_id=data['book_id'],
            chapter_number=data['chapter_number'],
            chunk_index=data['chunk_index'],
            speaker=data.get('speaker'),
            speed=data.get('speed'),
            status=JobStatus(data.get('status', 'pending')),
            error=data.get('error'),
            created_at=data.get('created_at'),
        )
    
    @classmethod
    def from_chunk(cls, chunk: Any, chapter_number: Optional[int] = None, status: Optional[JobStatus] = None) -> 'ChunkJob':
        """
        Create ChunkJob from Chunk or ChunkDB object.
        
        Args:
            chunk: Chunk or ChunkDB object
            chapter_number: Optional chapter number (if not in chunk)
            status: Optional job status (defaults to chunk.status or PENDING)
        """
        # Handle both Chunk (domain model) and ChunkDB (database model)
        book_id = chunk.book_id
        chunk_idx = chunk.index if hasattr(chunk, 'index') else chunk.chunk_index
        chunk_chapter = chapter_number if chapter_number is not None else (
            chunk.chapter_number if hasattr(chunk, 'chapter_number') else None
        )
        
        # Determine status
        if status:
            job_status = status
        elif hasattr(chunk, 'status'):
            # ChunkDB has status enum, Chunk has status enum
            chunk_status = chunk.status
            if isinstance(chunk_status, str):
                job_status = JobStatus(chunk_status)
            elif hasattr(chunk_status, 'value'):
                # Map ChunkStatus enum to JobStatus (they have same values)
                chunk_status_value = chunk_status.value
                job_status = JobStatus(chunk_status_value)
            elif isinstance(chunk_status, JobStatus):
                job_status = chunk_status
            else:
                job_status = JobStatus.PENDING
        else:
            job_status = JobStatus.PENDING
        
        # Get optional fields
        speaker = getattr(chunk, 'voice_name', None) or getattr(chunk, 'speaker', None)
        speed = getattr(chunk, 'speed', None)
        error = getattr(chunk, 'error', None)
        
        # Handle created_at (ChunkDB has datetime, need to convert to ISO string)
        created_at = None
        if hasattr(chunk, 'created_at') and chunk.created_at:
            if isinstance(chunk.created_at, str):
                created_at = chunk.created_at
            else:
                created_at = chunk.created_at.isoformat()
        
        return cls(
            book_id=book_id,
            chapter_number=chunk_chapter,
            chunk_index=chunk_idx,
            speaker=speaker,
            speed=speed,
            status=job_status,
            error=error,
            created_at=created_at,
        )

