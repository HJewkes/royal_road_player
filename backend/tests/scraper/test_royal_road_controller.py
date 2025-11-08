"""Unit tests for RoyalRoadController."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from src.scraper.royal_road_controller import RoyalRoadController
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


class TestRoyalRoadController:
    """Test cases for RoyalRoadController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self):
        """Create a RoyalRoadController with mocked dependencies."""
        with patch('src.scraper.royal_road_controller.RoyalRoadClient') as mock_client, \
             patch('src.scraper.royal_road_controller.HTMLProcessor') as mock_processor, \
             patch('src.scraper.royal_road_controller.BookController') as mock_book_ctrl, \
             patch('src.scraper.royal_road_controller.ChapterController') as mock_chapter_ctrl, \
             patch('src.scraper.royal_road_controller.MetricsCollector') as mock_metrics, \
             patch('src.scraper.royal_road_controller.get_settings') as mock_settings:
            
            controller = RoyalRoadController()
            controller.client = mock_client.return_value
            controller.processor = mock_processor.return_value
            controller.book_ctrl = mock_book_ctrl.return_value
            controller.chapter_ctrl = mock_chapter_ctrl.return_value
            controller.metrics = mock_metrics.return_value
            
            mock_settings.return_value.books_dir = Path("/tmp/books")
            mock_settings.return_value.scraper_delay_seconds = 0
            
            return controller
    
    def test_search(self, controller):
        """Test searching Royal Road."""
        mock_soup = Mock()
        controller.client.search.return_value = mock_soup
        controller.processor.extract_search_results.return_value = [
            SearchResult(title="Book 1", author="Author 1", url="https://rr.com/book1"),
            SearchResult(title="Book 2", author="Author 2", url="https://rr.com/book2"),
        ]
        
        results = controller.search("test query")
        
        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Book 1"
        controller.client.search.assert_called_once_with("test query")
    
    def test_get_book_preview(self, controller):
        """Test getting book preview."""
        mock_toc_soup = Mock()
        mock_chapter_soup = Mock()
        controller.client.get_table_of_contents.return_value = mock_toc_soup
        controller.client.get_chapter_page.return_value = mock_chapter_soup
        
        controller.processor.extract_chapters.return_value = [
            {"url": "https://rr.com/chapter1", "number": 1, "title": "Chapter 1"},
            {"url": "https://rr.com/chapter2", "number": 2, "title": "Chapter 2"},
        ]
        controller.processor.extract_chapter_preview.return_value = "Preview text..."
        
        preview = controller.get_book_preview("https://rr.com/book", book_number=7)
        
        assert isinstance(preview, BookPreview)
        assert preview.chapter_count == 2
        assert preview.preview_text == "Preview text..."
        assert len(preview.chapters) <= 20
        assert isinstance(preview.chapters[0], BookPreviewChapter)
    
    def test_find_book_in_series_success(self, controller):
        """Test finding a book in a series."""
        mock_soup = Mock()
        controller.client.get_table_of_contents.return_value = mock_soup
        
        controller.processor.extract_chapters.return_value = [
            {"url": "https://rr.com/fiction/12345/book/chapter/1/book-7", "number": 1, "title": "7.1 - Chapter"},
        ]
        controller.processor.filter_chapters_by_book.return_value = [
            {"url": "https://rr.com/fiction/12345/book/chapter/1/book-7", "number": 1, "title": "7.1 - Chapter"},
        ]
        controller.client.get_book_page.return_value = Mock()
        controller.processor.extract_book_title.return_value = "Book 7"
        
        result = controller.find_book_in_series("https://rr.com/series", 7)
        
        assert isinstance(result, FindBookInSeriesResult)
        assert result.book_number == 7
        assert result.book_title == "Book 7"
        assert result.chapter_count == 1
        assert result.error is None
    
    def test_find_book_in_series_not_found(self, controller):
        """Test finding a book that doesn't exist in series."""
        mock_soup = Mock()
        controller.client.get_table_of_contents.return_value = mock_soup
        
        controller.processor.extract_chapters.return_value = []
        controller.processor.filter_chapters_by_book.return_value = []
        
        result = controller.find_book_in_series("https://rr.com/series", 7)
        
        assert isinstance(result, FindBookInSeriesResult)
        assert result.error is not None
        assert "not found" in result.error.lower()
    
    def test_scrape_chapter(self, controller):
        """Test scraping a single chapter."""
        mock_soup = Mock()
        controller.client.get_chapter_page.return_value = mock_soup
        controller.processor.extract_chapter_content.return_value = "Chapter content here"
        
        # Mock title extraction
        title_elem = Mock()
        title_elem.get_text.return_value = "Chapter 1"
        mock_soup.find.return_value = title_elem
        
        result = controller.scrape_chapter("https://rr.com/chapter1", chapter_number=1)
        
        assert isinstance(result, ScrapeChapterResult)
        assert result.title == "Chapter 1"
        assert result.content == "Chapter content here"
        assert result.word_count > 0
        assert result.quality_ratio >= 0
    
    def test_scrape_book_success(self, controller, temp_dir):
        """Test scraping a book successfully."""
        # Setup mocks
        controller.processor.extract_book_id.return_value = "book_12345"
        controller.client.get_book_page.return_value = Mock()
        controller.processor.extract_book_title.return_value = "Test Book"
        controller.processor.sanitize_for_filesystem.return_value = "Test Book"
        
        controller.client.get_table_of_contents.return_value = Mock()
        controller.processor.extract_chapters.return_value = [
            {"url": "https://rr.com/chapter1", "number": 1, "title": "Chapter 1"},
        ]
        
        # Mock chapter scraping
        controller.scrape_chapter = Mock(return_value=ScrapeChapterResult(
            title="Chapter 1",
            content="Chapter content",
            word_count=2,
            quality_ratio=80.0,
        ))
        
        # Mock settings
        with patch('src.scraper.royal_road_controller.get_settings') as mock_settings:
            mock_settings.return_value.books_dir = temp_dir
            mock_settings.return_value.scraper_delay_seconds = 0
            
            result = controller.scrape_book("https://rr.com/book", max_chapters=1)
            
            assert isinstance(result, ScrapeBookResult)
            assert result.book_id == "book_12345"
            assert result.successful_chapters == 1
    
    def test_find_series_books(self, controller):
        """Test finding all books in a series."""
        mock_soup = Mock()
        controller.client.get_table_of_contents.return_value = mock_soup
        
        # Mock extract_chapters to return chapters with book numbers
        controller.processor.extract_chapters.return_value = [
            {"url": "https://rr.com/fiction/12345/book/chapter/1/book-7", "number": 1, "title": "7.1 - Chapter"},
            {"url": "https://rr.com/fiction/12345/book/chapter/2/book-8", "number": 2, "title": "8.1 - Chapter"},
        ]
        
        # Mock filter_chapters_by_book to return filtered chapters
        controller.processor.filter_chapters_by_book = Mock(side_effect=lambda chapters, book_num: [
            ch for ch in chapters if f"book-{book_num}" in ch['url'] or ch['title'].startswith(f"{book_num}.")
        ])
        
        result = controller.find_series_books("https://rr.com/book")
        
        assert isinstance(result, list)
        if result:  # If any books found
            assert isinstance(result[0], SeriesBook)
            assert result[0].book_number is not None
            assert result[0].in_system is False

