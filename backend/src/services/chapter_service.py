"""Service for managing individual chapter downloads."""

import logging
from typing import List, Optional

import attr

from src.controllers.book_controller import BookController
from src.controllers.chapter_controller import ChapterController
from src.models.chapter import Chapter
from src.models.responses import (
    ChapterInfo,
    ChapterStats,
    DownloadChapterResult,
)
from src.scraper.royal_road_controller import RoyalRoadController
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class ChapterService:
    """Service for downloading and managing individual chapters."""
    
    def __init__(self):
        """Initialize chapter service."""
        self.rr_ctrl = RoyalRoadController()
        self.book_ctrl = BookController()
        self.chapter_ctrl = ChapterController()
    
    def download_chapter(
        self,
        book_id: str,
        chapter_url: str,
        chapter_number: Optional[int] = None,
    ) -> DownloadChapterResult:
        """
        Download a single chapter.
        
        Args:
            book_id: Book identifier
            chapter_url: URL to the chapter page
            chapter_number: Optional chapter number
            
        Returns:
            Dictionary with chapter data and download result
        """
        logger.info(f"Downloading chapter from: {chapter_url}")
        
        # Verify book exists
        book = self.book_ctrl.get_book(book_id)
        if book is None:
            raise ValueError(f"Book not found: {book_id}")
        
        # Scrape chapter using Royal Road controller
        chapter_data = self.rr_ctrl.scrape_chapter(chapter_url, chapter_number)
        
        # Determine chapter number if not provided
        if chapter_number is None:
            # Use Royal Road number from chapter data (if available)
            chapter_number = 1  # Default to 1 if not provided
        
        # Create chapter directory structure
        settings = get_settings()
        book_dir = settings.books_dir / book.path if book.path else None
        if book_dir is None:
            # Find book directory
            for dir_path in settings.books_dir.iterdir():
                if dir_path.is_dir() and book_id in dir_path.name:
                    book_dir = dir_path
                    break
        
        if book_dir is None:
            raise ValueError(f"Book directory not found for {book_id}")
        
        # Create chapter directory (zero-padded)
        chapter_dir = book_dir / "chapters" / f"{chapter_number:02d}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        # Save chapter text file
        text_path = chapter_dir / "text.txt"
        text_path.write_text(chapter_data.content, encoding="utf-8")
        
        # Create chapter model and save
        chapter_title = chapter_data.title or f"Chapter {chapter_number}"
        chapter = Chapter(
            book_id=book_id,
            title=chapter_title,
            id=f"{book_id}_{chapter_number:02d}",
            chapter_number=chapter_number,
            number=None,  # Royal Road number not available from scrape_chapter result
            url=chapter_url,
            path=str(chapter_dir),
        )
        self.chapter_ctrl.save_chapter(chapter)
        
        word_count = chapter_data.word_count
        logger.info(f"✅ Chapter downloaded: {text_path} ({word_count} words)")
        
        return DownloadChapterResult(
            book_id=book_id,
            chapter_number=chapter_number,
            title=chapter_title,
            text_path=str(text_path),
            word_count=word_count,
            content_length=len(chapter_data.content),
        )
    
    def get_chapter_info(self, book_id: str, chapter_number: int) -> Optional[ChapterInfo]:
        """
        Get chapter information and metadata.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            ChapterInfo object or None if not found
        """
        chapter = self.chapter_ctrl.get_chapter(book_id, chapter_number)
        if chapter is None:
            return None
        
        # Get chapter statistics
        stats = self.chapter_ctrl.get_chapter_stats(book_id, chapter_number)
        if stats is None:
            return None
        
        # Get audio URLs
        audio_urls = self.get_chapter_audio_urls(book_id, chapter_number)
        
        return ChapterInfo(
            id=chapter.id,
            book_id=book_id,
            chapter_number=chapter_number,
            title=chapter.title,
            number=chapter.number,  # Royal Road number
            url=chapter.url,
            text_path=str(chapter.text_path) if chapter.text_path else None,
            audio_urls=audio_urls,
            has_text=chapter.has_text,
            word_count=chapter.word_count,
            is_chunked=chapter.is_chunked,
            chunk_count=chapter.chunk_count,
            has_audio=chapter.has_audio,
            stats=stats,
        )
    
    def discover_chapters(self, book_id: str, lightweight: bool = True, include_audio_urls: bool = False) -> List[dict]:
        """
        Discover chapters for a book.
        
        Args:
            book_id: Book identifier
            lightweight: If True, use fast metadata-only stats computation
            include_audio_urls: If True, include audio URLs (slower, scans filesystem)
            
        Returns:
            List of chapter dictionaries
        """
        chapters = self.book_ctrl.get_chapters(book_id)
        
        result = []
        for chapter in chapters:
            # Get chapter statistics (use lightweight mode by default for performance)
            stats = self.chapter_ctrl.get_chapter_stats(
                book_id, 
                chapter.chapter_number or 0,
                lightweight=lightweight
            )
            
            # Only get audio URLs if requested (this scans filesystem, so it's optional)
            audio_urls = []
            if include_audio_urls:
                audio_urls = self.get_chapter_audio_urls(book_id, chapter.chapter_number or 0)
            
            result.append({
                'id': chapter.id,
                'chapter_number': chapter.chapter_number,
                'title': chapter.title,
                'number': chapter.number,  # Royal Road number
                'url': chapter.url,
                'text_path': str(chapter.text_path) if chapter.text_path else None,
                'audio_urls': sorted(audio_urls) if audio_urls else [],
                'is_chunked': chapter.is_chunked,
                'chunk_count': chapter.chunk_count,
                'has_audio': chapter.has_audio,
                'scraped': chapter.has_text,
                'word_count': chapter.word_count,
                'duration_seconds': None,  # Would need to calculate from audio
            })
        
        return result
    
    def get_chapter_audio_urls(self, book_id: str, chapter_number: int) -> List[str]:
        """
        Get audio file URLs for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            List of audio file URLs (relative to /audio mount), sorted by chunk index
        """
        chapter = self.chapter_ctrl.get_chapter(book_id, chapter_number)
        if chapter is None or not chapter.has_audio:
            return []
        
        audio_urls_with_index = []
        if chapter.chunks_dir and chapter.chunks_dir.exists():
            # Find audio files in chunk directories
            settings = get_settings()
            for chunk_dir in chapter.chunks_dir.iterdir():
                if chunk_dir.is_dir() and chunk_dir.name.isdigit():
                    audio_file = chunk_dir / "audio.wav"
                    if audio_file.exists():
                        # Convert to URL relative to /audio mount
                        rel_path = audio_file.relative_to(settings.books_dir)
                        audio_url = f"/audio/{rel_path.as_posix()}"
                        # Extract chunk index for sorting
                        chunk_index = int(chunk_dir.name)
                        audio_urls_with_index.append((chunk_index, audio_url))
        
        # Sort by chunk index (numerically, not alphabetically)
        audio_urls_with_index.sort(key=lambda x: x[0])
        return [url for _, url in audio_urls_with_index]

