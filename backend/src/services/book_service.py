"""Service for managing book downloads and metadata."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from src.scraper.royal_road import RoyalRoadScraper
from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker

logger = logging.getLogger(__name__)


class BookService:
    """Service for downloading and managing books."""
    
    def __init__(self):
        """Initialize book service."""
        self.settings = get_settings()
        self.scraper = RoyalRoadScraper()
    
    def download_book(
        self,
        book_url: str,
        filter_book_number: Optional[int] = None,
        max_chapters: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Download all chapters for a book.
        
        Args:
            book_url: URL to the Royal Road book page
            filter_book_number: Optional book number to filter chapters
            max_chapters: Optional limit on number of chapters to download
            
        Returns:
            Dictionary with book metadata and download results
        """
        logger.info(f"Downloading book from: {book_url}")
        
        # Use scraper to download book
        result = self.scraper.scrape_book(
            book_url=book_url,
            output_dir=None,  # Use default directory
            max_chapters=max_chapters,
            filter_book_number=filter_book_number,
        )
        
        # Ensure metadata is properly initialized
        book_id = result.get('book_id')
        if book_id:
            # Find book directory
            book_dir = None
            for dir_path in self.settings.books_dir.iterdir():
                if dir_path.is_dir() and book_id in dir_path.name:
                    metadata_path = dir_path / "metadata.json"
                    if metadata_path.exists():
                        import json
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            if metadata.get('book_id') == book_id:
                                book_dir = dir_path
                                break
                        except Exception:
                            continue
            
            if book_dir:
                # Refresh metadata tracker to ensure consistency
                tracker = MetadataTracker(book_dir)
                tracker.refresh_from_filesystem()
        
        return result
    
    def get_book_info(self, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get book information and metadata.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Book metadata dictionary or None if not found
        """
        # Find book directory
        book_dir = None
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    import json
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            book_dir = dir_path
                            break
                    except Exception:
                        continue
        
        if not book_dir:
            return None
        
        tracker = MetadataTracker(book_dir)
        tracker.refresh_from_filesystem()
        metadata = tracker.load()
        
        return {
            'book_id': metadata.get('book_id'),
            'book_title': metadata.get('book_title'),
            'book_url': metadata.get('book_url'),
            'stats': tracker.get_stats(),
            'chapters': metadata.get('chapters', []),
        }

