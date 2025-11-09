"""Controller for chunk-level operations."""

import logging
from typing import Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class ChunkController:
    """Controller for chunk-level business logic operations."""
    
    def __init__(self, synchronizer: Optional[DataSynchronizer] = None):
        """
        Initialize chunk controller.
        
        Args:
            synchronizer: Optional DataSynchronizer instance (creates new one if not provided)
        """
        self.settings = get_settings()
        self.sync = synchronizer or DataSynchronizer(books_dir=self.settings.books_dir)
    
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
        return self.sync.load_chunk(book_id, chapter_number, chunk_index)
    
    def get_chunk_text(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[str]:
        """
        Get chunk text content.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk text content or None if not found
        """
        chunk = self.get_chunk(book_id, chapter_number, chunk_index)
        if chunk is None or not chunk.has_text:
            return None
        
        text_file = chunk.text_path
        if text_file is None:
            return None
        
        try:
            return text_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read chunk text: {e}")
            return None
    
    def update_status(
        self,
        book_id: str,
        chapter_number: int,
        chunk_index: int,
        status: ChunkStatus
    ) -> Optional[Chunk]:
        """
        Update chunk status.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            status: New status
            
        Returns:
            Updated Chunk instance or None if not found
        """
        return self.sync.update_chunk_status(book_id, chapter_number, chunk_index, status)
    
    def save_chunk(self, chunk: Chunk, chapter_number: Optional[int] = None) -> None:
        """
        Save chunk to database and filesystem.
        
        Args:
            chunk: Chunk instance to save
            chapter_number: Chapter number (extracted from chunk.chapter_id if not provided)
        """
        self.sync.save_chunk(chunk, chapter_number)

