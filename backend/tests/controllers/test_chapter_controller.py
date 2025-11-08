"""Unit tests for ChapterController."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil

from src.controllers.chapter_controller import ChapterController
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import ChapterStats


class TestChapterController:
    """Test cases for ChapterController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self):
        """Create a ChapterController with mocked DataSynchronizer."""
        with patch('src.controllers.chapter_controller.DataSynchronizer') as mock_sync:
            controller = ChapterController()
            controller.synchronizer = mock_sync.return_value
            return controller
    
    def test_get_chapter_success(self, controller):
        """Test getting a chapter that exists."""
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path="/path/to/chapter"
        )
        controller.synchronizer.load_chapter.return_value = mock_chapter
        
        chapter = controller.get_chapter("book_123", 1)
        
        assert chapter is not None
        assert chapter.chapter_number == 1
        controller.synchronizer.load_chapter.assert_called_once_with("book_123", 1)
    
    def test_get_chapter_not_found(self, controller):
        """Test getting a chapter that doesn't exist."""
        controller.synchronizer.load_chapter.return_value = None
        
        chapter = controller.get_chapter("book_123", 999)
        
        assert chapter is None
    
    def test_get_chunks(self, controller):
        """Test getting chunks for a chapter."""
        mock_chunks = [
            Chunk(index=1, book_id="book_123", text_start=0, text_end=100, status=ChunkStatus.PENDING),
            Chunk(index=2, book_id="book_123", text_start=100, text_end=200, status=ChunkStatus.COMPLETED),
        ]
        controller.synchronizer.load_chunks.return_value = mock_chunks
        
        chunks = controller.get_chunks("book_123", 1)
        
        assert len(chunks) == 2
        controller.synchronizer.load_chunks.assert_called_once_with("book_123", 1)
    
    def test_get_chapter_stats(self, controller, temp_dir):
        """Test getting chapter statistics."""
        chapter_dir = temp_dir / "chapter_01"
        chapter_dir.mkdir()
        text_file = chapter_dir / "text.txt"
        text_file.write_text("This is some test text content for the chapter.")
        
        chunks_dir = chapter_dir / "chunks"
        chunks_dir.mkdir()
        (chunks_dir / "1").mkdir()
        (chunks_dir / "2").mkdir()
        
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path=str(chapter_dir)
        )
        controller.synchronizer.load_chapter.return_value = mock_chapter
        
        # Create chunks with audio files for completed one
        chunk1_dir = chunks_dir / "1"
        (chunk1_dir / "audio.wav").write_bytes(b"fake audio")
        
        mock_chunks = [
            Chunk(index=1, book_id="book_123", text_start=0, text_end=20, status=ChunkStatus.COMPLETED, path=str(chunk1_dir)),
            Chunk(index=2, book_id="book_123", text_start=20, text_end=40, status=ChunkStatus.PENDING, path=str(chunks_dir / "2")),
        ]
        controller.synchronizer.load_chunks.return_value = mock_chunks
        
        stats = controller.get_chapter_stats("book_123", 1)
        
        assert stats is not None
        assert isinstance(stats, ChapterStats)
        assert stats.has_text is True
        assert stats.word_count > 0
        assert stats.is_chunked is True
        assert stats.chunk_count == 2
        assert stats.completed_chunks == 1  # Chunk 1 has COMPLETED status and audio file
        assert stats.pending_chunks == 1
    
    def test_get_chapter_stats_not_found(self, controller):
        """Test getting stats for non-existent chapter."""
        controller.synchronizer.load_chapter.return_value = None
        
        stats = controller.get_chapter_stats("book_123", 999)
        
        assert stats is None  # Returns None when chapter not found
    
    def test_get_chapter_text(self, controller, temp_dir):
        """Test getting chapter text content."""
        chapter_dir = temp_dir / "chapter_01"
        chapter_dir.mkdir()
        text_file = chapter_dir / "text.txt"
        text_file.write_text("Chapter text content here")
        
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path=str(chapter_dir)
        )
        controller.synchronizer.load_chapter.return_value = mock_chapter
        
        text = controller.get_chapter_text("book_123", 1)
        
        assert text == "Chapter text content here"
    
    def test_get_chapter_text_not_found(self, controller):
        """Test getting text for non-existent chapter."""
        controller.synchronizer.load_chapter.return_value = None
        
        text = controller.get_chapter_text("book_123", 999)
        
        assert text is None
    
    def test_save_chapter(self, controller):
        """Test saving a chapter."""
        chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path="/path/to/chapter"
        )
        
        controller.save_chapter(chapter)
        
        controller.synchronizer.save_chapter.assert_called_once_with(chapter)

