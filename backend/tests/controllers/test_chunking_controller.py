"""Unit tests for ChunkingController."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from src.controllers.chunking_controller import ChunkingController
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import ChunkingResult


class TestChunkingController:
    """Test cases for ChunkingController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self):
        """Create a ChunkingController with mocked dependencies."""
        with patch('src.controllers.chunking_controller.DataSynchronizer') as mock_sync, \
             patch('src.controllers.chunking_controller.get_settings') as mock_settings:
            mock_settings.return_value.books_dir = Path("/tmp/books")
            controller = ChunkingController()
            controller.sync = mock_sync.return_value
            return controller
    
    def test_chunk_chapter_success(self, controller, temp_dir):
        """Test chunking a chapter successfully."""
        # Setup chapter directory
        chapter_dir = temp_dir / "chapter_01"
        chapter_dir.mkdir(parents=True)
        text_file = chapter_dir / "text.txt"
        text_file.write_text("This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three.")
        
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            id="book_123_01",
            path=str(chapter_dir)
        )
        controller.sync.load_chapter.return_value = mock_chapter
        
        # Mock TextChunker
        mock_chunks = [
            Chunk(
                index=1,
                book_id="book_123",
                text_start=0,
                text_end=20,
                status=ChunkStatus.PENDING,
                chapter_id="book_123_01",
            ),
            Chunk(
                index=2,
                book_id="book_123",
                text_start=21,
                text_end=42,
                status=ChunkStatus.PENDING,
                chapter_id="book_123_01",
            ),
            Chunk(
                index=3,
                book_id="book_123",
                text_start=43,
                text_end=65,
                status=ChunkStatus.PENDING,
                chapter_id="book_123_01",
            ),
        ]
        
        with patch('src.controllers.chunking_controller.TextChunker') as mock_chunker_class:
            mock_chunker = mock_chunker_class.return_value
            mock_chunker.chunk_by_paragraphs.return_value = mock_chunks
            
            # Mock load_chunks to return the saved chunks
            controller.sync.load_chunks.return_value = mock_chunks
            
            result = controller.chunk_chapter(
                book_id="book_123",
                chapter_number=1,
                chunk_duration_minutes=1.0
            )
            
            assert isinstance(result, ChunkingResult)
            assert result.book_id == "book_123"
            assert result.chapter_number == 1
            assert result.chunk_count == 3
            assert result.total_text_length > 0
            # Note: chunks are saved but not returned in the result
            controller.sync.save_chunk.assert_called()
    
    def test_chunk_chapter_not_found(self, controller):
        """Test chunking a non-existent chapter."""
        controller.sync.load_chapter.return_value = None
        
        with pytest.raises(ValueError, match="Chapter.*not found"):
            controller.chunk_chapter("book_123", 999)
    
    def test_chunk_chapter_no_text(self, controller, temp_dir):
        """Test chunking a chapter without text file."""
        chapter_dir = temp_dir / "chapter_01"
        chapter_dir.mkdir(parents=True)
        # Don't create text.txt
        
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path=str(chapter_dir)
        )
        controller.sync.load_chapter.return_value = mock_chapter
        
        with pytest.raises(FileNotFoundError, match="Chapter text file not found"):
            controller.chunk_chapter("book_123", 1)
    
    def test_chunk_chapter_custom_params(self, controller, temp_dir):
        """Test chunking with custom parameters."""
        chapter_dir = temp_dir / "chapter_01"
        chapter_dir.mkdir(parents=True)
        text_file = chapter_dir / "text.txt"
        text_file.write_text("Short text.")
        
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            id="book_123_01",
            path=str(chapter_dir)
        )
        controller.sync.load_chapter.return_value = mock_chapter
        
        with patch('src.controllers.chunking_controller.TextChunker') as mock_chunker_class:
            mock_chunker = mock_chunker_class.return_value
            mock_chunker.chunk_by_paragraphs.return_value = [
                Chunk(
                    index=1,
                    book_id="book_123",
                    text_start=0,
                    text_end=11,
                    status=ChunkStatus.PENDING,
                    chapter_id="book_123_01",
                ),
            ]
            
            result = controller.chunk_chapter(
                book_id="book_123",
                chapter_number=1,
                target_chars=500,
                min_chars=100,
                max_chars=250
            )
            
            mock_chunker.chunk_by_paragraphs.assert_called_once()
            call_kwargs = mock_chunker.chunk_by_paragraphs.call_args[1]
            assert call_kwargs['target_chars_per_minute'] == 500
            assert call_kwargs['min_chars'] == 100
            assert call_kwargs['max_chars'] == 250

