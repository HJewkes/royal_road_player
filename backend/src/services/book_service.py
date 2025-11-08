"""Service for managing book downloads and metadata."""

import logging
import re
from typing import Optional, List

import attr

from src.scraper.royal_road_controller import RoyalRoadController
from src.controllers.book_controller import BookController
from src.models.responses import (
    BookSummary,
    BookInfo,
    BookChapterSummary,
    BookPreview,
    SearchResult,
    SeriesBook,
    ScrapeBookResult,
    FindBookInSeriesResult,
)

logger = logging.getLogger(__name__)


class BookService:
    """Service for downloading and managing books."""
    
    def __init__(self):
        """Initialize book service."""
        self.rr_ctrl = RoyalRoadController()
        self.book_ctrl = BookController()
    
    def download_book(
        self,
        book_url: str,
        filter_book_number: Optional[int] = None,
        max_chapters: Optional[int] = None,
    ) -> ScrapeBookResult:
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
        
        # Use Royal Road controller to scrape book
        result = self.rr_ctrl.scrape_book(
            book_url=book_url,
            output_dir=None,  # Use default directory
            max_chapters=max_chapters,
            filter_book_number=filter_book_number,
        )
        
        return result
    
    def get_book_info(self, book_id: str) -> Optional[BookInfo]:
        """
        Get book information and metadata.
        
        Args:
            book_id: Book identifier
            
        Returns:
            BookInfo object or None if not found
        """
        book = self.book_ctrl.get_book(book_id)
        if book is None:
            return None
        
        # Get book statistics
        stats = self.book_ctrl.get_book_stats(book_id)
        if stats is None:
            return None
        
        # Get chapters
        chapters = self.book_ctrl.get_chapters(book_id)
        
        return BookInfo(
            book_id=book.id,
            book_title=book.title,
            book_url=book.url,
            author=book.author,
            filter_book_number=book.filter_book_number,
            stats=stats,
            chapters=[
                BookChapterSummary(
                    chapter_number=ch.chapter_number,
                    title=ch.title,
                    number=ch.number,
                    url=ch.url,
                )
                for ch in chapters
            ],
        )
    
    def discover_books(self) -> List[BookSummary]:
        """
        Discover all books from the filesystem.
        
        Returns:
            List of BookSummary objects with metadata
        """
        books = self.book_ctrl.list_books()
        
        result = []
        for book in books:
            # Get book statistics
            stats = self.book_ctrl.get_book_stats(book.id)
            if stats is None:
                continue  # Skip books without stats
            
            result.append(BookSummary(
                id=book.id,
                title=book.title,
                author=book.author,
                url=book.url,
                chapter_count=book.chapter_count,
                path=book.path,
                stats=stats,
            ))
        
        return result
    
    def search_royal_road(self, query: str) -> List[SearchResult]:
        """
        Search Royal Road for a book.
        
        Args:
            query: Search query (book title or author)
            
        Returns:
            List of SearchResult objects with title, author, and URL
        """
        return self.rr_ctrl.search(query)
    
    def get_book_preview(self, book_url: str, book_number: Optional[int] = None) -> BookPreview:
        """
        Fetch preview information for a book from Royal Road.
        
        Args:
            book_url: URL to the Royal Road book page
            book_number: Optional book number to filter chapters
            
        Returns:
            BookPreview object with chapter_count, chapters, and preview_text
        """
        return self.rr_ctrl.get_book_preview(book_url, book_number)
    
    def find_book_in_series(self, series_url: str, book_number: int) -> FindBookInSeriesResult:
        """
        Find a specific book number in a Royal Road series.
        
        Args:
            series_url: URL to the series main page
            book_number: Book number to find (e.g., 7)
            
        Returns:
            FindBookInSeriesResult object with book information or error
        """
        return self.rr_ctrl.find_book_in_series(series_url, book_number)
    
    def find_series_books(self, book_id: str) -> List[SeriesBook]:
        """
        Find other books in the same series (both in system and from Royal Road).
        
        Args:
            book_id: Book ID to find series for
            
        Returns:
            List of book dictionaries in the same series
        """
        # Get target book
        target_book = self.book_ctrl.get_book(book_id)
        if target_book is None:
            return []
        
        target_url = target_book.url or ''
        target_title = target_book.title or ''
        
        # Extract base title (without "Book X" suffix)
        base_title_match = re.sub(r'\s*-\s*Book\s*\d+.*$', '', target_title, flags=re.I)
        base_title_match = re.sub(r'\s*\(book_\d+\)', '', base_title_match, flags=re.I).strip()
        
        # Extract fiction ID from URL
        url_match = re.search(r'/fiction/(\d+)', target_url) if target_url else None
        base_fiction_id = url_match.group(1) if url_match else None
        
        series_books = []
        books_in_system = {}  # Map book_number -> book dict
        
        # Add the current book to books_in_system first
        target_book_number = target_book.filter_book_number
        if target_book_number:
            # Check if book has audio
            chapters = self.book_ctrl.get_chapters(book_id)
            has_audio = any(ch.has_audio for ch in chapters)
            
            books_in_system[target_book_number] = {
                'id': book_id,
                'title': target_title,
                'book_number': target_book_number,
                'url': target_url,
                'has_audio': has_audio,
                'in_system': True,
            }
            series_books.append(books_in_system[target_book_number])
        
        # Look for other books with same base title or fiction ID (already in system)
        all_books = self.book_ctrl.list_books()
        for book in all_books:
            if book.id == book_id:
                continue
            
            book_url = book.url or ''
            book_title = book.title or ''
            
            # Check if same fiction ID
            is_same_series = False
            if base_fiction_id and book_url:
                other_url_match = re.search(r'/fiction/(\d+)', book_url)
                if other_url_match and other_url_match.group(1) == base_fiction_id:
                    is_same_series = True
            
            # Also check by base title similarity
            if not is_same_series and base_title_match:
                other_base_title = re.sub(r'\s*-\s*Book\s*\d+.*$', '', book_title, flags=re.I)
                other_base_title = re.sub(r'\s*\(book_\d+\)', '', other_base_title, flags=re.I).strip()
                if base_title_match.lower() == other_base_title.lower() and base_title_match:
                    is_same_series = True
            
            if is_same_series:
                book_number = book.filter_book_number
                
                # Check for audio
                chapters = self.book_ctrl.get_chapters(book.id)
                has_audio = any(ch.has_audio for ch in chapters)
                
                book_dict = SeriesBook(
                    id=book.id,
                    book_number=book_number,
                    url=book_url,
                    title=book_title,
                    in_system=True,
                    has_audio=has_audio,
                )
                series_books.append(book_dict)
                if book_number:
                    books_in_system[book_number] = book_dict
        
        # Fetch series books from Royal Road
        if target_url:
            royal_road_books = self.rr_ctrl.find_series_books(target_url)
            for rr_book in royal_road_books:
                book_num = rr_book.book_number
                # Check if this book is already in system (by book number)
                if book_num and book_num in books_in_system:
                    # Use the existing book info instead
                    existing_book = books_in_system[book_num]
                    # Update with Royal Road info if needed (create new object if URL missing)
                    if not existing_book.url:
                        updated_book = SeriesBook(
                            id=existing_book.id,
                            book_number=existing_book.book_number,
                            url=rr_book.url or target_url,
                            title=existing_book.title,
                            in_system=existing_book.in_system,
                            has_audio=existing_book.has_audio,
                        )
                        # Replace in list
                        series_books = [b if b.book_number != book_num else updated_book for b in series_books]
                        books_in_system[book_num] = updated_book
                    # Don't add duplicate
                    continue
                # Only add if not already in system
                if book_num:
                    series_books.append(rr_book)
        
        # Sort by book number
        series_books.sort(key=lambda x: x.book_number or 999)
        
        return series_books

