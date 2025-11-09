"""Service for generating TTS audio from chunks."""

import logging
from typing import Optional, List

from src.controllers.tts_controller import TTSController
from src.models.responses import AudioGenerationResult, ChapterAudioGenerationResult

logger = logging.getLogger(__name__)


class TTSChunkService:
    """Service for generating TTS audio from text chunks."""
    
    def __init__(self):
        """Initialize TTS chunk service."""
        self.tts_ctrl = TTSController()
    
    def generate_chunk_audio(
        self,
        book_id: str,
        chapter_number: int,
        chunk_index: int,
        speaker: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> AudioGenerationResult:
        """
        Generate audio for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            speaker: Optional speaker WAV file path
            speed: Optional playback speed (0.5-2.0, default 1.0)
            
        Returns:
            Dictionary with generation results
        """
        logger.info(f"Generating audio for chunk: {book_id}/{chapter_number}/chunk_{chunk_index}")
        
        # Use TTS controller
        result = self.tts_ctrl.generate_chunk_audio(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_index=chunk_index,
            speaker=speaker,
            speed=speed,
        )
        
        return result
    
    def generate_chapter_chunks(
        self,
        book_id: str,
        chapter_number: int,
        chunk_indices: Optional[List[int]] = None,
        speaker: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> ChapterAudioGenerationResult:
        """
        Generate audio for multiple chunks in a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_indices: Optional list of chunk indices to generate (defaults to all pending chunks)
            speaker: Optional speaker WAV file path
            speed: Optional playback speed (0.5-2.0, default 1.0)
            
        Returns:
            Dictionary with generation results
        """
        logger.info(f"Generating audio for chapter: {book_id}/{chapter_number}")
        
        # Use TTS controller
        result = self.tts_ctrl.generate_chapter_chunks(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_indices=chunk_indices,
            speaker=speaker,
            speed=speed,
        )
        
        return result

