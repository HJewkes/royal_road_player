"""Controller for book-level operations."""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.data.db_repository import BookRepository, ChapterRepository
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.responses import BookStats
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class BookController:
    """Controller for book-level business logic operations."""
    
    def __init__(self):
        """Initialize book controller."""
        self.settings = get_settings()
        # Simple cache for book stats (key: book_id, value: (stats, timestamp))
        self._stats_cache: Dict[str, tuple] = {}
        self._cache_ttl: float = 10.0  # Cache for 10 seconds
    
    def get_book(self, book_id: str) -> Optional[Book]:
        """
        Get a book by ID.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Book instance or None if not found
        """
        return BookRepository.get_by_id(book_id)
    
    def list_books(self) -> List[Book]:
        """
        List all books.
        
        Returns:
            List of Book instances
        """
        return BookRepository.get_all()
    
    def get_chapters(self, book_id: str) -> List[Chapter]:
        """
        Get all chapters for a book.
        
        Args:
            book_id: Book identifier
            
        Returns:
            List of Chapter instances
        """
        return ChapterRepository.get_by_book(book_id)
    
    def get_book_stats(self, book_id: str, lightweight: bool = False) -> Optional[BookStats]:
        """
        Get statistics for a book.
        
        Args:
            book_id: Book identifier
            lightweight: If True, use fast metadata-only counting (doesn't load full chunk objects)
            
        Returns:
            BookStats object or None if book not found
        """
        # Check cache first (only for lightweight mode)
        if lightweight:
            cache_key = f"{book_id}_lightweight"
            if cache_key in self._stats_cache:
                stats, timestamp = self._stats_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return stats
                # Cache expired, remove it
                del self._stats_cache[cache_key]
        
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
        
        # Use database for fast stats (much faster than reading files)
        from src.data.db_repository import ChunkRepository
        from src.models.enums import ChunkStatus
        
        if lightweight:
            # Fast path: use database aggregation query
            completed_chunks = ChunkRepository.count_by_status(
                book_id=book_id,
                status=ChunkStatus.COMPLETED
            )
        else:
            # Still use DB for speed, but could load full objects if needed
            completed_chunks = ChunkRepository.count_by_status(
                book_id=book_id,
                status=ChunkStatus.COMPLETED
            )
        
        stats = BookStats(
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
        
        # Cache the result (only for lightweight mode)
        if lightweight:
            cache_key = f"{book_id}_lightweight"
            self._stats_cache[cache_key] = (stats, time.time())
            # Limit cache size to prevent memory issues
            if len(self._stats_cache) > 100:
                # Remove oldest entries
                oldest_key = min(self._stats_cache.keys(), key=lambda k: self._stats_cache[k][1])
                del self._stats_cache[oldest_key]
        
        return stats
    
    def _count_completed_chunks_fast(self, book_id: str, chapters: List[Chapter]) -> int:
        """
        Fast method to count completed chunks by checking file existence only.
        Avoids reading metadata files when possible.
        
        Args:
            book_id: Book identifier
            chapters: List of chapters
            
        Returns:
            Count of completed chunks
        """
        from pathlib import Path
        
        completed_count = 0
        
        for chapter in chapters:
            if chapter.chapter_number is None or chapter.path is None:
                continue
            
            chunks_dir = Path(chapter.path) / "chunks"
            if not chunks_dir.exists():
                continue
            
            # Iterate through chunk directories
            for chunk_dir in chunks_dir.iterdir():
                if not chunk_dir.is_dir() or not chunk_dir.name.isdigit():
                    continue
                
                # Fast path: Check if audio file exists first (most common case)
                audio_file = chunk_dir / "audio.wav"
                if audio_file.exists():
                    # Audio exists, check metadata only if we need to verify status
                    metadata_path = chunk_dir / "metadata.json"
                    if metadata_path.exists():
                        try:
                            import json
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            # Only count if status is 'completed' (audio might exist but status might be different)
                            if metadata.get('status', 'pending') == 'completed':
                                completed_count += 1
                        except Exception:
                            # If metadata read fails but audio exists, assume completed
                            completed_count += 1
                    else:
                        # No metadata but audio exists - assume completed
                        completed_count += 1
        
        return completed_count
    
    def save_book(self, book: Book) -> None:
        """
        Save book to database and filesystem.
        
        Args:
            book: Book instance to save
        """
        # Save to database
        BookRepository.create_or_update(book)
        
        # Save metadata file to filesystem for backward compatibility
        from src.utils.file_operations import save_book_metadata
        save_book_metadata(book)

