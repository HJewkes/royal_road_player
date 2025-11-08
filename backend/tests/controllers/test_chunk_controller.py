"""Unit tests for ChunkController."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil

from src.controllers.chunk_controller import ChunkController
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus


class TestChunkController:
    """Test cases for ChunkController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self):
        """Create a ChunkController with mocked DataSynchronizer."""
        with patch('src.controllers.chunk_controller.DataSynchronizer') as mock_sync:
            controller = ChunkController()
            controller.synchronizer = mock_sync.return_value
            return controller
    
    def test_get_chunk_success(self, controller):
        """Test getting a chunk that exists."""
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=100,
            status=ChunkStatus.PENDING,
            path="/path/to/chunk"
        )
        controller.synchronizer.load_chunk.return_value = mock_chunk
        
        chunk = controller.get_chunk("book_123", 1, 1)
        
        assert chunk is not None
        assert chunk.index == 1
        controller.synchronizer.load_chunk.assert_called_once_with("book_123", 1, 1)
    
    def test_get_chunk_not_found(self, controller):
        """Test getting a chunk that doesn't exist."""
        controller.synchronizer.load_chunk.return_value = None
        
        chunk = controller.get_chunk("book_123", 1, 999)
        
        assert chunk is None
    
    def test_get_chunk_text(self, controller, temp_dir):
        """Test getting chunk text content."""
        chunk_dir = temp_dir / "chunks" / "1"
        chunk_dir.mkdir(parents=True)
        text_file = chunk_dir / "text.txt"
        text_file.write_text("Chunk text content")
        
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=20,
            status=ChunkStatus.PENDING,
            chapter_id="book_123_01",
            path=str(chunk_dir)
        )
        controller.synchronizer.load_chunk.return_value = mock_chunk
        
        text = controller.get_chunk_text("book_123", 1, 1)
        
        assert text == "Chunk text content"
    
    def test_update_status(self, controller):
        """Test updating chunk status."""
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=100,
            status=ChunkStatus.PENDING,
            path="/path/to/chunk"
        )
        controller.synchronizer.update_chunk_status.return_value = mock_chunk
        
        updated = controller.update_status("book_123", 1, 1, ChunkStatus.COMPLETED)
        
        assert updated is not None
        controller.synchronizer.update_chunk_status.assert_called_once_with(
            "book_123", 1, 1, ChunkStatus.COMPLETED
        )
    
    def test_flag_chunk(self, controller):
        """Test flagging a chunk."""
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=100,
            status=ChunkStatus.COMPLETED,
            flagged=False,
            path="/path/to/chunk"
        )
        controller.synchronizer.load_chunk.return_value = mock_chunk
        
        updated = controller.flag_chunk("book_123", 1, 1, flagged=True)
        
        assert updated is not None
        assert updated.flagged is True
        controller.synchronizer.save_chunk.assert_called_once()
    
    def test_flag_chunk_not_found(self, controller):
        """Test flagging a non-existent chunk."""
        controller.synchronizer.load_chunk.return_value = None
        
        result = controller.flag_chunk("book_123", 1, 999, flagged=True)
        
        assert result is None
    
    def test_save_chunk(self, controller):
        """Test saving a chunk."""
        chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=100,
            status=ChunkStatus.PENDING,
            path="/path/to/chunk"
        )
        
        controller.save_chunk(chunk)
        
        controller.synchronizer.save_chunk.assert_called_once_with(chunk)

