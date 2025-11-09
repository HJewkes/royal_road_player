"""Controller for chapter-level operations."""

import logging
from pathlib import Path
from typing import List, Optional

from src.data.db_repository import ChapterRepository, ChunkRepository
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.responses import ChapterStats
from src.utils.config import get_settings
from src.utils.file_operations import get_chapter_text

logger = logging.getLogger(__name__)


class ChapterController:
    """Controller for chapter-level business logic operations."""
    
    def __init__(self):
        """Initialize chapter controller."""
        self.settings = get_settings()
    
    def get_chapter(self, book_id: str, chapter_number: int) -> Optional[Chapter]:
        """
        Get a chapter by book ID and chapter number.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Chapter instance or None if not found
        """
        return ChapterRepository.get_by_book_and_number(book_id, chapter_number)
    
    def get_chunks(self, book_id: str, chapter_number: int) -> List[Chunk]:
        """
        Get all chunks for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            List of Chunk instances
        """
        return ChunkRepository.get_by_chapter(book_id, chapter_number)
    
    def get_chapter_stats(self, book_id: str, chapter_number: int, lightweight: bool = False) -> Optional[ChapterStats]:
        """
        Get statistics for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            lightweight: If True, use fast metadata-only counting (doesn't load full chunk objects)
            
        Returns:
            ChapterStats object or None if chapter not found
        """
        chapter = self.get_chapter(book_id, chapter_number)
        if chapter is None:
            return None
        
        # Use database for fast stats (much faster than reading files)
        from src.data.db_repository import ChunkRepository
        from src.models.enums import ChunkStatus
        
        # Get chunk counts from database (fast aggregation queries)
        total_chunks = chapter.chunk_count  # From chapter metadata
        completed_chunks = ChunkRepository.count_by_status(
            book_id=book_id,
            chapter_number=chapter_number,
            status=ChunkStatus.COMPLETED
        )
        pending_chunks = ChunkRepository.count_by_status(
            book_id=book_id,
            chapter_number=chapter_number,
            status=ChunkStatus.PENDING
        )
        failed_chunks = ChunkRepository.count_by_status(
            book_id=book_id,
            chapter_number=chapter_number,
            status=ChunkStatus.FAILED
        )
        
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
        )
    
    def _get_chapter_stats_fast(self, book_id: str, chapter_number: int, chapter: Chapter) -> Optional[ChapterStats]:
        """
        Fast method to get chapter stats by reading metadata files only.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chapter: Chapter object
            
        Returns:
            ChapterStats object or None if unable to compute
        """
        import json
        from pathlib import Path
        
        if chapter.path is None:
            return None
        
        chunks_dir = Path(chapter.path) / "chunks"
        if not chunks_dir.exists():
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
                total_chunks=0,
                completed_chunks=0,
                pending_chunks=0,
                failed_chunks=0,
            )
        
        total_chunks = 0
        completed_chunks = 0
        pending_chunks = 0
        failed_chunks = 0
        
        # Iterate through chunk directories
        for chunk_dir in chunks_dir.iterdir():
            if not chunk_dir.is_dir() or not chunk_dir.name.isdigit():
                continue
            
            total_chunks += 1
            metadata_path = chunk_dir / "metadata.json"
            
            if not metadata_path.exists():
                pending_chunks += 1
                continue
            
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                status = metadata.get('status', 'pending')
                audio_file = chunk_dir / "audio.wav"
                
                if status == 'completed' and audio_file.exists():
                    completed_chunks += 1
                elif status == 'pending':
                    pending_chunks += 1
                elif status == 'failed':
                    failed_chunks += 1
                else:
                    # Unknown status, count as pending
                    pending_chunks += 1
            except Exception:
                # Invalid metadata, count as pending
                pending_chunks += 1
        
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
        )
    
    def save_chapter(self, chapter: Chapter) -> None:
        """
        Save chapter to database and filesystem.
        
        Args:
            chapter: Chapter instance to save
        """
        # Save to database
        ChapterRepository.create_or_update(chapter)
        
        # Save metadata file to filesystem for backward compatibility
        from src.utils.file_operations import save_chapter_metadata
        save_chapter_metadata(chapter)
    
    def get_chapter_text(self, book_id: str, chapter_number: int) -> Optional[str]:
        """
        Get chapter text content from filesystem.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Chapter text content or None if not found
        """
        chapter = self.get_chapter(book_id, chapter_number)
        if chapter is None:
            return None
        return get_chapter_text(chapter)

