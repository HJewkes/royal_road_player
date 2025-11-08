"""Unit tests for BookController."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from src.controllers.book_controller import BookController
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.responses import BookStats


class TestBookController:
    """Test cases for BookController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self, temp_dir):
        """Create a BookController with mocked DataSynchronizer."""
        with patch('src.controllers.book_controller.DataSynchronizer') as mock_sync:
            controller = BookController()
            controller.synchronizer = mock_sync.return_value
            return controller
    
    def test_list_books(self, controller):
        """Test listing all books."""
        mock_books = [
            Book(id="book_1", title="Book 1", path="/path/to/book1"),
            Book(id="book_2", title="Book 2", path="/path/to/book2"),
        ]
        controller.synchronizer.load_books.return_value = mock_books
        
        books = controller.list_books()
        
        assert len(books) == 2
        assert books[0].id == "book_1"
        controller.synchronizer.load_books.assert_called_once()
    
    def test_get_book_success(self, controller):
        """Test getting a book that exists."""
        mock_book = Book(id="book_123", title="Test Book", path="/path/to/book")
        controller.synchronizer.load_book.return_value = mock_book
        
        book = controller.get_book("book_123")
        
        assert book is not None
        assert book.id == "book_123"
        controller.synchronizer.load_book.assert_called_once_with("book_123")
    
    def test_get_book_not_found(self, controller):
        """Test getting a book that doesn't exist."""
        controller.synchronizer.load_book.return_value = None
        
        book = controller.get_book("nonexistent")
        
        assert book is None
    
    def test_get_chapters(self, controller):
        """Test getting chapters for a book."""
        mock_chapters = [
            Chapter(book_id="book_123", title="Chapter 1", chapter_number=1),
            Chapter(book_id="book_123", title="Chapter 2", chapter_number=2),
        ]
        controller.synchronizer.load_chapters.return_value = mock_chapters
        
        chapters = controller.get_chapters("book_123")
        
        assert len(chapters) == 2
        controller.synchronizer.load_chapters.assert_called_once_with("book_123")
    
    def test_get_book_stats(self, controller, temp_dir):
        """Test getting book statistics."""
        mock_book = Book(
            id="book_123",
            title="Test Book",
            path=str(temp_dir / "Test Book (book_123)")
        )
        controller.synchronizer.load_book.return_value = mock_book
        
        mock_chapters = [
            Chapter(book_id="book_123", title="Chapter 1", chapter_number=1, path=str(temp_dir / "ch1")),
            Chapter(book_id="book_123", title="Chapter 2", chapter_number=2, path=str(temp_dir / "ch2")),
        ]
        controller.synchronizer.load_chapters.return_value = mock_chapters
        
        # Create mock text files
        (temp_dir / "ch1" / "text.txt").parent.mkdir(parents=True)
        (temp_dir / "ch1" / "text.txt").write_text("Some text content here")
        (temp_dir / "ch2" / "text.txt").parent.mkdir(parents=True)
        (temp_dir / "ch2" / "text.txt").write_text("More text")
        
        stats = controller.get_book_stats("book_123")
        
        assert stats is not None
        assert isinstance(stats, BookStats)
        assert stats.total_chapters == 2
        assert stats.chapters_with_text == 2
        assert stats.chapters_with_audio >= 0
        assert stats.chapters_chunked >= 0
    
    def test_get_book_stats_book_not_found(self, controller):
        """Test getting stats for non-existent book."""
        controller.synchronizer.load_book.return_value = None
        
        stats = controller.get_book_stats("nonexistent")
        
        assert stats is None  # Returns None when book not found
    
    def test_save_book(self, controller):
        """Test saving a book."""
        book = Book(id="book_123", title="Test Book", path="/path/to/book")
        
        controller.save_book(book)
        
        controller.synchronizer.save_book.assert_called_once_with(book)

