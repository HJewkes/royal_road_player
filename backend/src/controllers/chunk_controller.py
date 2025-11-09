"""Controller for chunk-level operations."""

import logging
from typing import Optional

from src.data.db_repository import ChunkRepository
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.utils.config import get_settings
from src.utils.file_operations import get_chunk_text

logger = logging.getLogger(__name__)


class ChunkController:
    """Controller for chunk-level business logic operations."""
    
    def __init__(self):
        """Initialize chunk controller."""
        self.settings = get_settings()
    
    def get_chunk(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[Chunk]:
        """
        Get a chunk by book ID, chapter number, and chunk index.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk instance or None if not found
        """
        return ChunkRepository.get_by_book_chapter_index(book_id, chapter_number, chunk_index)
    
    def get_chunk_text(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[str]:
        """
        Get chunk text content from filesystem.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk text content or None if not found
        """
        chunk = self.get_chunk(book_id, chapter_number, chunk_index)
        if chunk is None:
            return None
        return get_chunk_text(chunk)
    
    def update_status(
        self,
        book_id: str,
        chapter_number: int,
        chunk_index: int,
        status: ChunkStatus
    ) -> Optional[Chunk]:
        """
        Update chunk status in database.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            status: New status
            
        Returns:
            Updated Chunk instance or None if not found
        """
        # Update status in database
        success = ChunkRepository.update_status(book_id, chapter_number, chunk_index, status)
        if not success:
            return None
        
        # Reload chunk to return updated instance
        chunk = self.get_chunk(book_id, chapter_number, chunk_index)
        if chunk:
            # Update metadata file on filesystem for backward compatibility
            from src.utils.file_operations import save_chunk_metadata
            save_chunk_metadata(chunk)
        return chunk
    
    def save_chunk(self, chunk: Chunk, chapter_number: Optional[int] = None) -> None:
        """
        Save chunk to database and filesystem.
        
        Args:
            chunk: Chunk instance to save
            chapter_number: Chapter number (extracted from chunk.chapter_id if not provided)
        """
        # Extract chapter_number from chunk.chapter_id if not provided
        if chapter_number is None and chunk.chapter_id:
            parts = chunk.chapter_id.split('_')
            if len(parts) >= 2:
                try:
                    chapter_number = int(parts[-1])
                except ValueError:
                    pass
        
        # Save to database
        ChunkRepository.create_or_update(chunk, chapter_number)
        
        # Save metadata file to filesystem for backward compatibility
        from src.utils.file_operations import save_chunk_metadata
        save_chunk_metadata(chunk)

