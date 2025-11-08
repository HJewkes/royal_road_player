"""Service for chunking chapter text into segments."""

import logging
from typing import Optional

from src.controllers.chunking_controller import ChunkingController
from src.controllers.chunk_controller import ChunkController
from src.models.responses import ChunkingResult

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking chapter text into segments for TTS processing."""
    
    def __init__(self):
        """Initialize chunking service."""
        self.chunking_ctrl = ChunkingController()
        self.chunk_ctrl = ChunkController()
    
    def chunk_chapter(
        self,
        book_id: str,
        chapter_number: int,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> ChunkingResult:
        """
        Chunk a chapter's text into segments.
        
        This creates chunk metadata and saves chunk text files but does NOT generate audio.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            Dictionary with chunking results
        """
        logger.info(f"Chunking chapter: {book_id}/{chapter_number}")
        
        # Use chunking controller
        result = self.chunking_ctrl.chunk_chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_duration_minutes=chunk_duration_minutes,
            target_chars=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        
        return result
    
    def get_chunk_text(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[str]:
        """
        Get the text content for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk text content or None if not found
        """
        return self.chunk_ctrl.get_chunk_text(book_id, chapter_number, chunk_index)

