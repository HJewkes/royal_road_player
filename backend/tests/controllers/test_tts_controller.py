"""Unit tests for TTSController."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from src.controllers.tts_controller import TTSController
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import AudioGenerationResult, ChapterAudioGenerationResult


class TestTTSController:
    """Test cases for TTSController."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def controller(self):
        """Create a TTSController with mocked dependencies."""
        with patch('src.controllers.tts_controller.DataSynchronizer') as mock_sync, \
             patch('src.controllers.tts_controller.get_tts_engine') as mock_engine, \
             patch('src.controllers.tts_controller.load_voice_registry') as mock_voice_reg, \
             patch('src.controllers.tts_controller.get_settings') as mock_settings:
            
            mock_engine.return_value.is_loaded.return_value = True
            mock_voice_reg.return_value = {}
            mock_settings.return_value.books_dir = Path("/tmp/books")
            mock_settings.return_value.tts_speed = 1.0
            
            controller = TTSController()
            controller.sync = mock_sync.return_value
            controller.engine = mock_engine.return_value
            return controller
    
    def test_generate_chunk_audio_success(self, controller, temp_dir):
        """Test generating audio for a chunk successfully."""
        chunk_dir = temp_dir / "chunk_1"
        chunk_dir.mkdir(parents=True)
        text_file = chunk_dir / "text.txt"
        text_file.write_text("Chunk text content")
        # Don't create audio file - we want to test generation
        audio_file = chunk_dir / "audio.wav"
        
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=20,
            status=ChunkStatus.PENDING,
            chapter_id="book_123_01",
            path=str(chunk_dir)
        )
        controller.sync.load_chunk.return_value = mock_chunk
        
        # Mock the updated chunk after status change
        updated_chunk_running = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=20,
            status=ChunkStatus.RUNNING,
            chapter_id="book_123_01",
            path=str(chunk_dir)
        )
        controller.sync.update_chunk_status.return_value = updated_chunk_running
        
        # Mock synthesize to create the file
        def mock_synthesize(*args, **kwargs):
            audio_file.write_bytes(b"fake audio")
            return audio_file
        
        controller.engine.synthesize.side_effect = mock_synthesize
        
        result = controller.generate_chunk_audio("book_123", 1, 1)
        
        assert isinstance(result, AudioGenerationResult)
        assert result.chunk_index == 1
        assert result.status == 'completed'
        assert result.path is not None
        controller.engine.synthesize.assert_called_once()
    
    def test_generate_chunk_audio_chunk_not_found(self, controller):
        """Test generating audio for non-existent chunk."""
        controller.sync.load_chunk.return_value = None
        
        with pytest.raises(ValueError, match="Chunk.*not found"):
            controller.generate_chunk_audio("book_123", 1, 999)
    
    def test_generate_chunk_audio_already_completed(self, controller, temp_dir):
        """Test skipping already completed chunk."""
        chunk_dir = temp_dir / "chunk_1"
        chunk_dir.mkdir(parents=True)
        audio_file = chunk_dir / "audio.wav"
        audio_file.write_bytes(b"fake audio data")
        
        mock_chunk = Chunk(
            index=1,
            book_id="book_123",
            text_start=0,
            text_end=20,
            status=ChunkStatus.COMPLETED,
            chapter_id="book_123_01",
            path=str(chunk_dir)
        )
        controller.sync.load_chunk.return_value = mock_chunk
        
        result = controller.generate_chunk_audio("book_123", 1, 1)
        
        assert isinstance(result, AudioGenerationResult)
        assert result.skipped is True
        assert result.status == 'completed'
        controller.engine.synthesize.assert_not_called()
    
    def test_generate_chapter_chunks_all_pending(self, controller):
        """Test generating audio for all pending chunks in a chapter."""
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path="/path/to/chapter"
        )
        controller.sync.load_chapter.return_value = mock_chapter
        
        mock_chunks = [
            Chunk(index=1, book_id="book_123", text_start=0, text_end=100, status=ChunkStatus.PENDING, path="/chunk1"),
            Chunk(index=2, book_id="book_123", text_start=100, text_end=200, status=ChunkStatus.PENDING, path="/chunk2"),
        ]
        controller.sync.load_chunks.return_value = mock_chunks
        
        # Mock generate_chunk_audio to return AudioGenerationResult
        # Need to handle the actual method signature
        def mock_generate(book_id, chapter_number, chunk_index, **kwargs):
            return AudioGenerationResult(
                chunk_index=chunk_index,
                status='completed',
                path=f'/chunk{chunk_index}/audio.wav'
            )
        controller.generate_chunk_audio = Mock(side_effect=mock_generate)
        
        result = controller.generate_chapter_chunks("book_123", 1)
        
        assert isinstance(result, ChapterAudioGenerationResult)
        assert result.chapter_number == 1
        assert result.generated == 2
        assert len(result.chunks) == 2
    
    def test_generate_chapter_chunks_specific_indices(self, controller):
        """Test generating audio for specific chunk indices."""
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path="/path/to/chapter"
        )
        controller.sync.load_chapter.return_value = mock_chapter
        
        mock_chunks = [
            Chunk(index=1, book_id="book_123", text_start=0, text_end=100, status=ChunkStatus.PENDING, path="/chunk1"),
            Chunk(index=2, book_id="book_123", text_start=100, text_end=200, status=ChunkStatus.COMPLETED, path="/chunk2"),
            Chunk(index=3, book_id="book_123", text_start=200, text_end=300, status=ChunkStatus.PENDING, path="/chunk3"),
        ]
        controller.sync.load_chunks.return_value = mock_chunks
        
        controller.generate_chunk_audio = Mock(return_value=AudioGenerationResult(
            chunk_index=1,
            status=ChunkStatus.COMPLETED.value
        ))
        
        result = controller.generate_chapter_chunks("book_123", 1, chunk_indices=[1, 3])
        
        assert isinstance(result, ChapterAudioGenerationResult)
        assert result.generated == 2
        assert controller.generate_chunk_audio.call_count == 2
    
    def test_generate_chapter_chunks_no_chunks(self, controller):
        """Test generating audio when chapter has no chunks."""
        mock_chapter = Chapter(
            book_id="book_123",
            title="Chapter 1",
            chapter_number=1,
            path="/path/to/chapter"
        )
        controller.sync.load_chapter.return_value = mock_chapter
        controller.sync.load_chunks.return_value = []
        
        with pytest.raises(ValueError, match="has no chunks"):
            controller.generate_chapter_chunks("book_123", 1)

