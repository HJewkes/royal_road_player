"""Controller for TTS audio generation operations."""

import logging
import time
from pathlib import Path
from typing import List, Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import AudioGenerationResult, ChapterAudioGenerationResult
from src.tts.engine import get_tts_engine
from src.tts.voice_registry import load_voice_registry
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class TTSController:
    """Controller for TTS audio generation operations."""
    
    def __init__(self, synchronizer: Optional[DataSynchronizer] = None):
        """
        Initialize TTS controller.
        
        Args:
            synchronizer: Optional DataSynchronizer instance (creates new one if not provided)
        """
        self.settings = get_settings()
        self.sync = synchronizer or DataSynchronizer(books_dir=self.settings.books_dir)
        self.engine = get_tts_engine()
        self.voice_registry = load_voice_registry()
        # Get default voice from registry (narrator or first available)
        self._default_speaker = self.voice_registry.get('narrator') or (
            list(self.voice_registry.values())[0] if self.voice_registry else None
        )
    
    def generate_chunk_audio(
        self,
        book_id: str,
        chapter_number: int,
        chunk_index: int,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> AudioGenerationResult:
        """
        Generate audio for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            speaker: Optional speaker WAV file path
            language: Optional language code
            speed: Optional playback speed
            emotion: Optional emotion parameter
            
        Returns:
            Dictionary with generation results
            
        Raises:
            ValueError: If book, chapter, or chunk not found
        """
        logger.info(f"Generating audio for chunk: {book_id}/{chapter_number}/chunk_{chunk_index}")
        
        # Load chunk
        chunk = self.sync.load_chunk(book_id, chapter_number, chunk_index)
        if chunk is None:
            raise ValueError(f"Chunk {chunk_index} not found for chapter {chapter_number}")
        
        # Check if chunk already has audio
        if chunk.has_audio:
            logger.info(f"Chunk {chunk_index} already has audio, skipping")
            return AudioGenerationResult(
                chunk_index=chunk_index,
                status='completed',
                path=str(chunk.audio_path) if chunk.audio_path else None,
                skipped=True,
            )
        
        # Get chunk text
        if not chunk.has_text:
            raise ValueError(f"Chunk {chunk_index} text file not found")
        
        text_file = chunk.text_path
        if text_file is None:
            raise ValueError("Chunk text path is None")
        
        chunk_text = text_file.read_text(encoding='utf-8')
        
        # Update chunk status to running
        updated_chunk = self.sync.update_chunk_status(
            book_id, chapter_number, chunk_index, ChunkStatus.RUNNING
        )
        if updated_chunk is None:
            raise ValueError("Failed to update chunk status")
        
        # Load model if not already loaded
        if not self.engine.is_loaded():
            logger.info("Loading TTS model...")
            self.engine.load_model()
        
        # Use default speaker if none provided
        if speaker is None and self._default_speaker:
            speaker = self._default_speaker.speaker_wav
            logger.info(f"Using default speaker: {self._default_speaker.name}")
        
        # Get audio output path
        audio_path = chunk.audio_path
        if audio_path is None:
            raise ValueError("Chunk audio path is None")
        
        # Ensure directory exists
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate audio
        try:
            start_time = time.time()
            
            generated_path = self.engine.synthesize(
                text=chunk_text,
                output_path=audio_path,
                annotations=None,
                speaker=speaker,
                language=language or self.settings.tts_language,
                speed=speed or self.settings.tts_speed,
                emotion=emotion or self.settings.tts_emotion,
            )
            
            generation_time = time.time() - start_time
            
            # Update chunk status to completed
            # Note: We need to update the chunk with generation_time_seconds
            # Since models are frozen, we need to create a new instance
            completed_chunk = Chunk(
                index=chunk.index,
                book_id=chunk.book_id,
                text_start=chunk.text_start,
                text_end=chunk.text_end,
                status=ChunkStatus.COMPLETED,
                chapter_id=chunk.chapter_id,
                path=chunk.path,
                generation_time_seconds=generation_time,
                flagged=chunk.flagged,
            )
            self.sync.save_chunk(completed_chunk)
            
            logger.info(f"✅ Generated audio for chunk {chunk_index}: {generated_path}")
            
            return AudioGenerationResult(
                chunk_index=chunk_index,
                status='completed',
                path=str(generated_path),
                generation_time_seconds=generation_time,
                file_size_mb=generated_path.stat().st_size / (1024 * 1024),
            )
            
        except Exception as e:
            logger.error(f"Failed to generate audio for chunk {chunk_index}: {e}")
            
            # Update chunk status to failed
            self.sync.update_chunk_status(
                book_id, chapter_number, chunk_index, ChunkStatus.FAILED
            )
            
            raise
    
    def generate_chapter_chunks(
        self,
        book_id: str,
        chapter_number: int,
        chunk_indices: Optional[List[int]] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> ChapterAudioGenerationResult:
        """
        Generate audio for multiple chunks in a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_indices: Optional list of chunk indices to generate (defaults to all pending chunks)
            speaker: Optional speaker WAV file path
            language: Optional language code
            speed: Optional playback speed
            emotion: Optional emotion parameter
            
        Returns:
            Dictionary with generation results
            
        Raises:
            ValueError: If book or chapter not found
        """
        logger.info(f"Generating audio for chapter: {book_id}/{chapter_number}")
        
        # Load chunks
        chunks = self.sync.load_chunks(book_id, chapter_number)
        
        if not chunks:
            raise ValueError(f"Chapter {chapter_number} has no chunks. Chunk the chapter first.")
        
        # Determine which chunks to generate
        if chunk_indices is None:
            # Generate all pending chunks
            chunk_indices = [ch.index for ch in chunks if ch.is_pending]
        
        if not chunk_indices:
            logger.info("No chunks to generate")
            return ChapterAudioGenerationResult(
                book_id=book_id,
                chapter_number=chapter_number,
                generated=0,
                skipped=0,
                failed=0,
            )
        
        # Generate audio for each chunk
        generated_count = 0
        skipped_count = 0
        failed_count = 0
        chunk_results = []
        
        for chunk_index in chunk_indices:
            try:
                result = self.generate_chunk_audio(
                    book_id=book_id,
                    chapter_number=chapter_number,
                    chunk_index=chunk_index,
                    speaker=speaker,
                    language=language,
                    speed=speed,
                    emotion=emotion,
                )
                chunk_results.append(result)
                if result.skipped:
                    skipped_count += 1
                else:
                    generated_count += 1
            except Exception as e:
                logger.error(f"Failed to generate chunk {chunk_index}: {e}")
                failed_count += 1
                chunk_results.append(AudioGenerationResult(
                    chunk_index=chunk_index,
                    status='failed',
                ))
        
        logger.info(f"✅ Generated {generated_count} chunks, skipped {skipped_count}, failed {failed_count}")
        
        return ChapterAudioGenerationResult(
            book_id=book_id,
            chapter_number=chapter_number,
            generated=generated_count,
            skipped=skipped_count,
            failed=failed_count,
            chunks=chunk_results,
        )

