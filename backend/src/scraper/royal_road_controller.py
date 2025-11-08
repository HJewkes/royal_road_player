"""Controller for Royal Road operations - consolidates business logic."""

import logging
import re
import signal
import sys
import time
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin

from src.controllers.book_controller import BookController
from src.controllers.chapter_controller import ChapterController
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.responses import (
    BookPreview,
    BookPreviewChapter,
    SearchResult,
    SeriesBook,
    ScrapeChapterResult,
    ScrapeBookResult,
    FindBookInSeriesResult,
)
from src.scraper.html_processor import HTMLProcessor
from src.scraper.royal_road_client import RoyalRoadClient
from src.utils.config import get_settings
from src.utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class RoyalRoadController:
    """Controller for Royal Road operations - business logic consolidation."""
    
    def __init__(self):
        """Initialize Royal Road controller."""
        self.settings = get_settings()
        self.client = RoyalRoadClient()
        self.processor = HTMLProcessor()
        self.book_ctrl = BookController()
        self.chapter_ctrl = ChapterController()
        self.metrics = MetricsCollector()
        self._should_stop = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully."""
        logger.warning("Interrupt received. Stopping gracefully...")
        self._should_stop = True
        sys.exit(130)  # Standard exit code for SIGINT
    
    def search(self, query: str) -> List[SearchResult]:
        """
        Search Royal Road for books.
        
        Args:
            query: Search query (book title or author)
            
        Returns:
            List of book dictionaries with title, author, and URL
        """
        try:
            soup = self.client.search(query)
            return self.processor.extract_search_results(soup)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_book_preview(self, book_url: str, book_number: Optional[int] = None) -> BookPreview:
        """
        Get preview information for a book from Royal Road.
        
        Args:
            book_url: URL to the Royal Road book page
            book_number: Optional book number to filter chapters
            
        Returns:
            BookPreview object with chapter_count, chapters, and preview_text
        """
        try:
            soup = self.client.get_table_of_contents(book_url)
            
            # Extract chapters
            chapters = self.processor.extract_chapters(soup, book_url, filter_book_number=book_number)
            
            # Get preview text from first chapter
            preview_text = ""
            if chapters:
                try:
                    first_chapter_url = chapters[0]['url']
                    chapter_soup = self.client.get_chapter_page(first_chapter_url)
                    preview_text = self.processor.extract_chapter_preview(chapter_soup, max_length=500)
                except Exception as e:
                    logger.debug(f"Failed to fetch preview text: {e}")
            
            # Convert chapter dicts to BookPreviewChapter objects
            preview_chapters = [
                BookPreviewChapter(title=ch['title'], url=ch['url'])
                for ch in chapters[:20]  # Limit to first 20 for preview
            ]
            
            return BookPreview(
                chapter_count=len(chapters),
                chapters=preview_chapters,
                preview_text=preview_text,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch book preview: {e}")
            return BookPreview(
                chapter_count=0,
                chapters=[],
                preview_text='',
            )
    
    def find_book_in_series(self, series_url: str, book_number: int) -> FindBookInSeriesResult:
        """
        Find a specific book number in a Royal Road series.
        
        Args:
            series_url: URL to the series main page
            book_number: Book number to find (e.g., 7)
            
        Returns:
            FindBookInSeriesResult object with book information or error
        """
        try:
            soup = self.client.get_table_of_contents(series_url)
            chapters = self.processor.extract_chapters(soup, series_url)
            
            # Filter chapters by book number
            filtered_chapters = self.processor.filter_chapters_by_book(chapters, book_number)
            
            if not filtered_chapters:
                return FindBookInSeriesResult(
                    book_number=book_number,
                    book_title="",
                    book_url="",
                    chapter_count=0,
                    error=f'Book {book_number} not found in series',
                )
            
            # Extract book info from first chapter URL
            first_chapter = filtered_chapters[0]
            chapter_url = first_chapter['url']
            
            # Extract fiction ID from URL
            match = re.search(r'/fiction/(\d+)', chapter_url)
            if not match:
                return FindBookInSeriesResult(
                    book_number=book_number,
                    book_title="",
                    book_url="",
                    chapter_count=0,
                    error='Could not extract fiction ID from chapter URL',
                )
            
            fiction_id = match.group(1)
            book_url = f"https://www.royalroad.com/fiction/{fiction_id}"
            
            # Get book title
            book_soup = self.client.get_book_page(book_url)
            book_title = self.processor.extract_book_title(book_soup, book_url)
            
            return FindBookInSeriesResult(
                book_number=book_number,
                book_title=book_title,
                book_url=book_url,
                chapter_count=len(filtered_chapters),
            )
        except Exception as e:
            logger.error(f"Failed to find book in series: {e}")
            return FindBookInSeriesResult(
                book_number=book_number,
                book_title="",
                book_url="",
                chapter_count=0,
                error=str(e),
            )
    
    def scrape_chapter(self, chapter_url: str, chapter_number: Optional[int] = None) -> ScrapeChapterResult:
        """
        Scrape a single chapter from Royal Road.
        
        Args:
            chapter_url: URL to the chapter page
            chapter_number: Optional chapter number for logging
            
        Returns:
            ScrapeChapterResult object with chapter content and metadata
            
        Raises:
            RuntimeError: If scraping fails
        """
        try:
            soup = self.client.get_chapter_page(chapter_url)
            
            # Extract title
            title_elem = (
                soup.find("h1", class_=re.compile(r"chapter.*title", re.I))
                or soup.find("h1")
                or soup.find("h2", class_=re.compile(r"chapter.*title", re.I))
            )
            title = title_elem.get_text(strip=True) if title_elem else f"Chapter {chapter_number or 'Unknown'}"
            
            # Extract content
            text = self.processor.extract_chapter_content(soup)
            
            # Calculate text quality
            total_chars = len(text)
            clean_chars = len(text.replace("\n", "").replace(" ", ""))
            quality_ratio = (clean_chars / total_chars * 100) if total_chars > 0 else 0.0
            
            self.metrics.record_text_quality(quality_ratio)
            
            return ScrapeChapterResult(
                title=title,
                content=text,
                word_count=len(text.split()),
                quality_ratio=quality_ratio,
            )
        except Exception as e:
            error_msg = f"Failed to scrape chapter: {e}"
            self.metrics.record_chapter_download(
                success=False, error=error_msg, chapter_number=chapter_number
            )
            raise RuntimeError(error_msg) from e
    
    def scrape_book(
        self,
        book_url: str,
        output_dir: Optional[Path] = None,
        max_chapters: Optional[int] = None,
        filter_book_number: Optional[int] = None,
    ) -> ScrapeBookResult:
        """
        Scrape all chapters from a Royal Road book and save to new nested structure.
        
        Args:
            book_url: URL to the Royal Road book page
            output_dir: Directory to save book (defaults to data/books/{book_id})
            max_chapters: Optional limit on number of chapters to scrape
            filter_book_number: Optional book number to filter chapters
            
        Returns:
            Dictionary with book metadata and scraping results
        """
        self.metrics.start()
        
        try:
            # Extract book ID
            book_id = self.processor.extract_book_id(book_url)
            
            # Get book title
            book_soup = self.client.get_book_page(book_url)
            book_title = self.processor.extract_book_title(book_soup, book_url)
            
            # Determine output directory
            if output_dir is None:
                safe_title = self.processor.sanitize_for_filesystem(book_title)
                if filter_book_number:
                    safe_title = f"{safe_title} - Book {filter_book_number}"
                dir_name = f"{safe_title} ({book_id})"
                output_dir = self.settings.books_dir / dir_name
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Get all chapters
            logger.info(f"Fetching all chapters for {book_id}...")
            toc_soup = self.client.get_table_of_contents(book_url)
            all_chapters = self.processor.extract_chapters(toc_soup, book_url)
            logger.info(f"Found {len(all_chapters)} total chapters")
            
            # Filter by book number if specified
            if filter_book_number:
                logger.info(f"Filtering for Book {filter_book_number}...")
                chapter_list = self.processor.filter_chapters_by_book(all_chapters, filter_book_number)
                logger.info(f"Found {len(chapter_list)} chapters in Book {filter_book_number}")
            else:
                chapter_list = all_chapters
            
            if max_chapters:
                chapter_list = chapter_list[:max_chapters]
                logger.info(f"Limiting to first {max_chapters} chapters")
            
            # Create book model and save
            book = Book(
                id=book_id,
                title=book_title,
                url=book_url,
                filter_book_number=filter_book_number,
                path=str(output_dir),
            )
            self.book_ctrl.save_book(book)
            
            # Scrape each chapter
            successful_chapters = []
            failed_chapters = []
            
            logger.info(f"Starting to scrape {len(chapter_list)} chapters...")
            
            for idx, chapter_info in enumerate(chapter_list, 1):
                if self._should_stop:
                    logger.warning(f"Stopping at user request. Scraped {idx-1}/{len(chapter_list)} chapters.")
                    break
                
                chapter_num = chapter_info["number"]
                chapter_url = chapter_info["url"]
                chapter_title = chapter_info["title"]
                
                logger.info(f"[{idx}/{len(chapter_list)}] Scraping Chapter {chapter_num}: {chapter_title}")
                
                try:
                    # Scrape chapter
                    chapter_data = self.scrape_chapter(chapter_url, chapter_num)
                    
                    # Determine chapter number for directory (use Royal Road number or sequential)
                    chapter_dir_number = chapter_num if chapter_num else idx
                    
                    # Create chapter directory (zero-padded)
                    chapter_dir = output_dir / "chapters" / f"{chapter_dir_number:02d}"
                    chapter_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save chapter text file
                    text_path = chapter_dir / "text.txt"
                    text_path.write_text(chapter_data.content, encoding="utf-8")
                    
                    # Create chapter model and save
                    chapter = Chapter(
                        book_id=book_id,
                        title=chapter_data.title,
                        id=f"{book_id}_{chapter_dir_number:02d}",
                        chapter_number=chapter_dir_number,
                        number=chapter_num,  # Royal Road number
                        url=chapter_url,
                        path=str(chapter_dir),
                    )
                    self.chapter_ctrl.save_chapter(chapter)
                    
                    # Record success
                    bytes_downloaded = len(chapter_data.content.encode("utf-8"))
                    self.metrics.record_chapter_download(
                        success=True, bytes_downloaded=bytes_downloaded, chapter_number=chapter_num
                    )
                    
                    successful_chapters.append({
                        "number": chapter_num,
                        "chapter_number": chapter_dir_number,
                        "title": chapter_data.title,
                        "word_count": chapter_data.word_count,
                    })
                    
                    # Rate limiting
                    if idx < len(chapter_list):
                        time.sleep(self.settings.scraper_delay_seconds)
                
                except Exception as e:
                    logger.error(f"Failed to scrape Chapter {chapter_num}: {e}")
                    failed_chapters.append({"number": chapter_num, "error": str(e)})
                    self.metrics.record_chapter_download(
                        success=False, error=str(e), chapter_number=chapter_num
                    )
            
            # Save metrics report
            metrics_path = self.metrics.save_report(f"{book_id}_scraper_metrics.json")
            self.metrics.print_summary()
            
            return ScrapeBookResult(
                book_id=book_id,
                book_title=book_title,
                book_url=book_url,
                filter_book_number=filter_book_number,
                total_chapters_available=len(all_chapters),
                chapters_to_scrape=len(chapter_list),
                successful_chapters=len(successful_chapters),
                failed_chapters=len(failed_chapters),
                output_dir=str(output_dir),
                metrics_path=str(metrics_path),
            )
        
        except Exception as e:
            self.metrics.stop()
            raise RuntimeError(f"Failed to scrape book: {e}") from e
    
    def find_series_books(self, book_url: str) -> List[SeriesBook]:
        """
        Find all books in a series from Royal Road by analyzing chapter URLs.
        
        Args:
            book_url: URL to the Royal Road book page
            
        Returns:
            List of SeriesBook objects with book_number and inferred URLs
        """
        try:
            soup = self.client.get_table_of_contents(book_url)
            chapters = self.processor.extract_chapters(soup, book_url)
            
            # Extract fiction ID
            fiction_match = re.search(r'/fiction/(\d+)', book_url)
            if not fiction_match:
                return []
            fiction_id = fiction_match.group(1)
            
            # Analyze chapters to find book numbers
            book_numbers = set()
            for chapter in chapters:
                href = chapter.get("url", "")
                title = chapter.get("title", "")
                
                # Method 1: Look for /book-X pattern in URL
                book_match = re.search(r'/book-(\d+)', href, re.I)
                if book_match:
                    book_numbers.add(int(book_match.group(1)))
                
                # Method 2: Look for book numbers in chapter titles
                # Pattern: XX-YY where XX is book number
                title_book_match = re.search(r'^(\d{1,2})-\d+', title)
                if title_book_match:
                    book_numbers.add(int(title_book_match.group(1)))
                
                # Pattern: X.Y where X is book number
                title_book_match2 = re.search(r'^(\d+)\.\d+', title)
                if title_book_match2:
                    book_numbers.add(int(title_book_match2.group(1)))
                
                # Pattern: "Book X" in title
                title_book_match3 = re.search(r'\bBook\s*(\d+)\b', title, re.I)
                if title_book_match3:
                    book_numbers.add(int(title_book_match3.group(1)))
            
            # Build list of series books
            series_books = []
            for book_num in sorted(book_numbers):
                series_books.append(SeriesBook(
                    book_number=book_num,
                    url=book_url,  # Same URL, filter by book number when scraping
                    title=f"Book {book_num}",  # Will be updated when scraped
                    in_system=False,
                ))
            
            return series_books
        
        except Exception as e:
            logger.warning(f"Failed to fetch series from Royal Road: {e}")
            return []

