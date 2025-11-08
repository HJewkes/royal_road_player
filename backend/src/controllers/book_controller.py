"""Controller for book-level operations."""

import logging
from pathlib import Path
from typing import List, Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.responses import BookStats
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class BookController:
    """Controller for book-level business logic operations."""
    
    def __init__(self, synchronizer: Optional[DataSynchronizer] = None):
        """
        Initialize book controller.
        
        Args:
            synchronizer: Optional DataSynchronizer instance (creates new one if not provided)
        """
        self.settings = get_settings()
        self.sync = synchronizer or DataSynchronizer(books_dir=self.settings.books_dir)
    
    def get_book(self, book_id: str) -> Optional[Book]:
        """
        Get a book by ID.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Book instance or None if not found
        """
        return self.sync.load_book(book_id)
    
    def list_books(self) -> List[Book]:
        """
        List all books.
        
        Returns:
            List of Book instances
        """
        return self.sync.load_books()
    
    def get_chapters(self, book_id: str) -> List[Chapter]:
        """
        Get all chapters for a book.
        
        Args:
            book_id: Book identifier
            
        Returns:
            List of Chapter instances
        """
        return self.sync.load_chapters(book_id)
    
    def get_book_stats(self, book_id: str) -> Optional[BookStats]:
        """
        Get statistics for a book.
        
        Args:
            book_id: Book identifier
            
        Returns:
            BookStats object or None if book not found
        """
        book = self.get_book(book_id)
        if book is None:
            return None
        
        chapters = self.get_chapters(book_id)
        
        # Compute statistics
        total_chapters = len(chapters)
        chapters_with_text = sum(1 for ch in chapters if ch.has_text)
        chapters_with_audio = sum(1 for ch in chapters if ch.has_audio)
        chapters_chunked = sum(1 for ch in chapters if ch.is_chunked)
        
        total_chunks = sum(ch.chunk_count for ch in chapters)
        completed_chunks = 0
        for chapter in chapters:
            if chapter.chapter_number is None:
                continue
            chunks = self.sync.load_chunks(book_id, chapter.chapter_number)
            completed_chunks += sum(1 for ch in chunks if ch.is_completed)
        
        return BookStats(
            book_id=book.id,
            title=book.title,
            total_chapters=total_chapters,
            chapters_with_text=chapters_with_text,
            chapters_with_audio=chapters_with_audio,
            chapters_chunked=chapters_chunked,
            total_chunks=total_chunks,
            completed_chunks=completed_chunks,
            pending_chunks=total_chunks - completed_chunks,
        )
    
    def save_book(self, book: Book) -> None:
        """
        Save book to filesystem.
        
        Args:
            book: Book instance to save
        """
        self.sync.save_book(book)

