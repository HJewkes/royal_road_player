"""Service for managing individual chapter downloads."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from src.scraper.royal_road import RoyalRoadScraper
from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker

logger = logging.getLogger(__name__)


class ChapterService:
    """Service for downloading and managing individual chapters."""
    
    def __init__(self):
        """Initialize chapter service."""
        self.settings = get_settings()
        self.scraper = RoyalRoadScraper()
    
    def find_book_dir(self, book_id: str) -> Optional[Path]:
        """
        Find book directory by book_id.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Path to book directory or None if not found
        """
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    import json
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            return dir_path
                    except Exception:
                        continue
        return None
    
    def download_chapter(
        self,
        book_id: str,
        chapter_url: str,
        chapter_number: Optional[int] = None,
    ) -> Dict[str, Any]:
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
        
        # Find book directory
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        # Scrape chapter
        chapter_data = self.scraper.scrape_chapter(chapter_url, chapter_number)
        
        # Save chapter text file
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        from src.scraper.royal_road import sanitize_chapter_filename
        chapter_title = chapter_data.get("title", f"Chapter {chapter_number or 'Unknown'}")
        text_filename = sanitize_chapter_filename(chapter_number or 0, chapter_title)
        text_path = chapters_dir / text_filename
        text_path.write_text(chapter_data["content"], encoding="utf-8")
        
        # Update metadata
        tracker = MetadataTracker(book_dir)
        word_count = len(chapter_data["content"].split())
        tracker.mark_chapter_scraped(text_filename.replace('.txt', ''), word_count)
        
        logger.info(f"✅ Chapter downloaded: {text_path}")
        
        return {
            'chapter_title': text_filename.replace('.txt', ''),
            'text_path': str(text_path),
            'word_count': word_count,
            'content_length': len(chapter_data["content"]),
        }
    
    def get_chapter_info(self, book_id: str, chapter_title: str) -> Optional[Dict[str, Any]]:
        """
        Get chapter information and metadata.
        
        Args:
            book_id: Book identifier
            chapter_title: Chapter title (filename without extension)
            
        Returns:
            Chapter metadata dictionary or None if not found
        """
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            return None
        
        tracker = MetadataTracker(book_dir)
        metadata = tracker.load()
        
        chapter_meta = next(
            (ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title),
            None
        )
        
        if not chapter_meta:
            return None
        
        # Check if text file exists
        chapters_dir = book_dir / "chapters"
        text_file = chapters_dir / f"{chapter_title}.txt"
        
        return {
            'title': chapter_title,
            'scraped': chapter_meta.get('scraped', False),
            'has_audio': chapter_meta.get('has_audio', False),
            'is_chunked': chapter_meta.get('is_chunked', False),
            'chunk_count': chapter_meta.get('chunk_count', 0),
            'chunk_metadata': chapter_meta.get('chunk_metadata', []),
            'text_file_exists': text_file.exists(),
            'text_length': len(text_file.read_text(encoding='utf-8')) if text_file.exists() else 0,
        }

