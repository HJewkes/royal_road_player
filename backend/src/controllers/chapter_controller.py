"""Controller for chapter-level operations."""

import logging
from pathlib import Path
from typing import List, Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.responses import ChapterStats
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class ChapterController:
    """Controller for chapter-level business logic operations."""
    
    def __init__(self, synchronizer: Optional[DataSynchronizer] = None):
        """
        Initialize chapter controller.
        
        Args:
            synchronizer: Optional DataSynchronizer instance (creates new one if not provided)
        """
        self.settings = get_settings()
        self.sync = synchronizer or DataSynchronizer(books_dir=self.settings.books_dir)
    
    def get_chapter(self, book_id: str, chapter_number: int) -> Optional[Chapter]:
        """
        Get a chapter by book ID and chapter number.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Chapter instance or None if not found
        """
        return self.sync.load_chapter(book_id, chapter_number)
    
    def get_chunks(self, book_id: str, chapter_number: int) -> List[Chunk]:
        """
        Get all chunks for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            List of Chunk instances
        """
        return self.sync.load_chunks(book_id, chapter_number)
    
    def get_chapter_stats(self, book_id: str, chapter_number: int) -> Optional[ChapterStats]:
        """
        Get statistics for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            ChapterStats object or None if chapter not found
        """
        chapter = self.get_chapter(book_id, chapter_number)
        if chapter is None:
            return None
        
        chunks = self.get_chunks(book_id, chapter_number)
        
        # Compute statistics
        total_chunks = len(chunks)
        completed_chunks = sum(1 for ch in chunks if ch.is_completed)
        pending_chunks = sum(1 for ch in chunks if ch.is_pending)
        failed_chunks = sum(1 for ch in chunks if ch.is_failed)
        flagged_chunks = sum(1 for ch in chunks if ch.is_flagged)
        
        return ChapterStats(
            book_id=book_id,
            chapter_number=chapter_number,
            title=chapter.title,
            has_text=chapter.has_text,
            word_count=chapter.word_count,
            text_size=chapter.text_size,
            is_chunked=chapter.is_chunked,
            chunk_count=chapter.chunk_count,
            has_audio=chapter.has_audio,
            total_chunks=total_chunks,
            completed_chunks=completed_chunks,
            pending_chunks=pending_chunks,
            failed_chunks=failed_chunks,
            flagged_chunks=flagged_chunks,
        )
    
    def save_chapter(self, chapter: Chapter) -> None:
        """
        Save chapter to filesystem.
        
        Args:
            chapter: Chapter instance to save
        """
        self.sync.save_chapter(chapter)
    
    def get_chapter_text(self, book_id: str, chapter_number: int) -> Optional[str]:
        """
        Get chapter text content.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Chapter text content or None if not found
        """
        chapter = self.get_chapter(book_id, chapter_number)
        if chapter is None or not chapter.has_text:
            return None
        
        text_file = chapter.text_path
        if text_file is None:
            return None
        
        try:
            return text_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read chapter text: {e}")
            return None

