"""Unit tests for DataSynchronizer."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import shutil

from src.data.data_synchronizer import DataSynchronizer
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus


class TestDataSynchronizer:
    """Test cases for DataSynchronizer."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def synchronizer(self, temp_dir):
        """Create a DataSynchronizer with temporary directory."""
        with patch('src.data.data_synchronizer.get_settings') as mock_settings:
            mock_settings.return_value.books_dir = temp_dir
            return DataSynchronizer()
    
    def test_load_books_empty(self, synchronizer, temp_dir):
        """Test loading books when none exist."""
        books = synchronizer.load_books()
        assert books == []
    
    def test_load_book_not_found(self, synchronizer):
        """Test loading non-existent book."""
        book = synchronizer.load_book("nonexistent_book")
        assert book is None
    
    def test_save_and_load_book(self, synchronizer, temp_dir):
        """Test saving and loading a book."""
        book = Book(
            id="book_12345",
            title="Test Book",
            author="Test Author",
            url="https://royalroad.com/fiction/12345/book",
            path=str(temp_dir / "Test Book (book_12345)")
        )
        
        # Create directory
        book_dir = temp_dir / "Test Book (book_12345)"
        book_dir.mkdir(parents=True)
        
        synchronizer.save_book(book)
        
        # Load it back
        loaded_book = synchronizer.load_book("book_12345")
        
        assert loaded_book is not None
        assert loaded_book.id == book.id
        assert loaded_book.title == book.title
        assert loaded_book.author == book.author
    
    def test_save_and_load_chapter(self, synchronizer, temp_dir):
        """Test saving and loading a chapter."""
        # Setup book directory
        book_dir = temp_dir / "Test Book (book_12345)"
        book_dir.mkdir(parents=True)
        
        # Create book metadata first
        book_metadata = {
            "book_id": "book_12345",
            "book_title": "Test Book",
        }
        (book_dir / "metadata.json").write_text(json.dumps(book_metadata), encoding='utf-8')
        
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir()
        chapter_dir = chapters_dir / "01"
        chapter_dir.mkdir()
        
        # Create chapter metadata
        metadata = {
            "id": "book_12345_01",
            "book_id": "book_12345",
            "title": "Chapter 1",
            "chapter_number": 1,
            "number": 1,
            "url": "https://royalroad.com/fiction/12345/book/chapter/1",
        }
        (chapter_dir / "metadata.json").write_text(json.dumps(metadata), encoding='utf-8')
        
        chapter = synchronizer.load_chapter("book_12345", 1)
        
        assert chapter is not None
        assert chapter.book_id == "book_12345"
        assert chapter.chapter_number == 1
        assert chapter.title == "Chapter 1"
    
    def test_save_and_load_chunks(self, synchronizer, temp_dir):
        """Test saving and loading chunks."""
        # Setup structure
        book_dir = temp_dir / "Test Book (book_12345)"
        book_dir.mkdir(parents=True)
        
        # Create book metadata
        book_metadata = {
            "book_id": "book_12345",
            "book_title": "Test Book",
        }
        (book_dir / "metadata.json").write_text(json.dumps(book_metadata), encoding='utf-8')
        
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir()
        chapter_dir = chapters_dir / "01"
        chapter_dir.mkdir()
        
        # Create chapter metadata
        chapter_metadata = {
            "id": "book_12345_01",
            "book_id": "book_12345",
            "title": "Chapter 1",
            "chapter_number": 1,
        }
        (chapter_dir / "metadata.json").write_text(json.dumps(chapter_metadata), encoding='utf-8')
        
        chunks_dir = chapter_dir / "chunks"
        chunks_dir.mkdir()
        chunk_dir = chunks_dir / "1"
        chunk_dir.mkdir()
        
        # Create chunk metadata
        metadata = {
            "index": 1,
            "book_id": "book_12345",
            "chapter_id": "book_12345_01",
            "text_start": 0,
            "text_end": 100,
            "status": "pending",
        }
        (chunk_dir / "metadata.json").write_text(json.dumps(metadata), encoding='utf-8')
        
        chunks = synchronizer.load_chunks("book_12345", 1)
        
        assert len(chunks) == 1
        assert chunks[0].index == 1
        assert chunks[0].text_start == 0
        assert chunks[0].text_end == 100
        assert chunks[0].status == ChunkStatus.PENDING
    
    def test_update_chunk_status(self, synchronizer, temp_dir):
        """Test updating chunk status."""
        # Setup structure
        book_dir = temp_dir / "Test Book (book_12345)"
        book_dir.mkdir(parents=True)
        
        # Create book metadata
        book_metadata = {
            "book_id": "book_12345",
            "book_title": "Test Book",
        }
        (book_dir / "metadata.json").write_text(json.dumps(book_metadata), encoding='utf-8')
        
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir()
        chapter_dir = chapters_dir / "01"
        chapter_dir.mkdir()
        
        # Create chapter metadata
        chapter_metadata = {
            "id": "book_12345_01",
            "book_id": "book_12345",
            "title": "Chapter 1",
            "chapter_number": 1,
        }
        (chapter_dir / "metadata.json").write_text(json.dumps(chapter_metadata), encoding='utf-8')
        
        chunks_dir = chapter_dir / "chunks"
        chunks_dir.mkdir()
        chunk_dir = chunks_dir / "1"
        chunk_dir.mkdir()
        
        # Create initial chunk
        metadata = {
            "index": 1,
            "book_id": "book_12345",
            "chapter_id": "book_12345_01",
            "text_start": 0,
            "text_end": 100,
            "status": "pending",
        }
        (chunk_dir / "metadata.json").write_text(json.dumps(metadata), encoding='utf-8')
        
        # Update status
        updated_chunk = synchronizer.update_chunk_status("book_12345", 1, 1, ChunkStatus.COMPLETED)
        
        assert updated_chunk is not None
        assert updated_chunk.status == ChunkStatus.COMPLETED
        
        # Verify it was saved
        saved_metadata = json.loads((chunk_dir / "metadata.json").read_text())
        assert saved_metadata["status"] == "completed"
    
    def test_chunk_status_enum_conversion(self, synchronizer, temp_dir):
        """Test that chunk status is correctly converted between enum and string."""
        # Setup structure
        book_dir = temp_dir / "Test Book (book_12345)"
        book_dir.mkdir(parents=True)
        
        # Create book metadata
        book_metadata = {
            "book_id": "book_12345",
            "book_title": "Test Book",
        }
        (book_dir / "metadata.json").write_text(json.dumps(book_metadata), encoding='utf-8')
        
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir()
        chapter_dir = chapters_dir / "01"
        chapter_dir.mkdir()
        
        # Create chapter metadata
        chapter_metadata = {
            "id": "book_12345_01",
            "book_id": "book_12345",
            "title": "Chapter 1",
            "chapter_number": 1,
        }
        (chapter_dir / "metadata.json").write_text(json.dumps(chapter_metadata), encoding='utf-8')
        
        chunks_dir = chapter_dir / "chunks"
        chunks_dir.mkdir()
        chunk_dir = chunks_dir / "1"
        chunk_dir.mkdir()
        
        # Create chunk with string status
        metadata = {
            "index": 1,
            "book_id": "book_12345",
            "chapter_id": "book_12345_01",
            "text_start": 0,
            "text_end": 100,
            "status": "completed",  # String, not enum
        }
        (chunk_dir / "metadata.json").write_text(json.dumps(metadata), encoding='utf-8')
        
        # Load should convert to enum
        chunk = synchronizer.load_chunk("book_12345", 1, 1)
        
        assert chunk.status == ChunkStatus.COMPLETED
        assert isinstance(chunk.status, ChunkStatus)

