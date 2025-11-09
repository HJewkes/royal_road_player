"""Service for chunking chapter text into segments."""

import logging
from pathlib import Path
from typing import List, Optional

from src.controllers.chunking_controller import ChunkingController
from src.controllers.chunk_controller import ChunkController
from src.models.responses import ChunkingResult

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking chapter text into segments for TTS processing."""
    
    def __init__(self):
        """Initialize chunking service."""
        self.chunking_ctrl = ChunkingController()
        self.chunk_ctrl = ChunkController()
    
    def chunk_chapter(
        self,
        book_id: str,
        chapter_number: int,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> ChunkingResult:
        """
        Chunk a chapter's text into segments.
        
        This creates chunk metadata and saves chunk text files but does NOT generate audio.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            ChunkingResult with chunks included
        """
        logger.info(f"Chunking chapter: {book_id}/{chapter_number}")
        
        # Use chunking controller
        result = self.chunking_ctrl.chunk_chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_duration_minutes=chunk_duration_minutes,
            target_chars=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        
        return result
    
    def clear_chunks_and_audio(
        self,
        book_id: str,
        chapter_number: int,
    ) -> None:
        """
        Clear all chunks and audio files for a chapter.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
        """
        logger.info(f"Clearing chunks and audio for chapter: {book_id}/{chapter_number}")
        self.chunking_ctrl.clear_chunks_and_audio(book_id, chapter_number)
    
    def rechunk_chapter(
        self,
        book_id: str,
        chapter_number: int,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> ChunkingResult:
        """
        Rechunk a chapter by clearing old chunks/audio and creating new ones.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            ChunkingResult with new chunks included
        """
        logger.info(f"Rechunking chapter: {book_id}/{chapter_number}")
        return self.chunking_ctrl.rechunk_chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_duration_minutes=chunk_duration_minutes,
            target_chars=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
        )
    
    def get_chunk_text(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[str]:
        """
        Get the text content for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk text content or None if not found
        """
        return self.chunk_ctrl.get_chunk_text(book_id, chapter_number, chunk_index)
    
    def backfill_chunk_durations(
        self,
        book_id: str,
        chapter_number: int,
    ) -> dict:
        """
        Backfill audio_duration_seconds for existing chunks by reading from audio files.
        
        This reads durations from existing WAV files and updates chunk metadata without
        regenerating audio. Only updates chunks that have audio files but missing durations.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Dictionary with backfill statistics:
            {
                'total_chunks': int,
                'chunks_with_audio': int,
                'chunks_updated': int,
                'chunks_already_had_duration': int,
                'chunks_missing_audio': int,
                'errors': int
            }
        """
        logger.info(f"Backfilling chunk durations for {book_id}/chapter_{chapter_number}")
        
        # Load all chunks for the chapter
        from src.controllers.chapter_controller import ChapterController
        chapter_ctrl = ChapterController()
        chunks = chapter_ctrl.get_chunks(book_id, chapter_number)
        
        stats = {
            'total_chunks': len(chunks),
            'chunks_with_audio': 0,
            'chunks_updated': 0,
            'chunks_already_had_duration': 0,
            'chunks_missing_audio': 0,
            'errors': 0,
        }
        
        for chunk in chunks:
            # Skip if chunk doesn't have audio file
            if not chunk.has_audio or not chunk.audio_path:
                stats['chunks_missing_audio'] += 1
                continue
            
            stats['chunks_with_audio'] += 1
            
            # Skip if already has duration
            if chunk.audio_duration_seconds is not None and chunk.audio_duration_seconds > 0:
                stats['chunks_already_had_duration'] += 1
                continue
            
            # Read duration from WAV file
            try:
                audio_path = Path(chunk.audio_path)
                if not audio_path.exists():
                    logger.warning(f"Audio file does not exist: {audio_path}")
                    stats['chunks_missing_audio'] += 1
                    continue
                
                from src.utils.file_operations import get_audio_duration
                duration = get_audio_duration(audio_path)
                
                if duration and duration > 0:
                    # Update chunk with duration
                    from src.models.chunk import Chunk
                    from src.models.enums import ChunkStatus
                    
                    updated_chunk = Chunk(
                        index=chunk.index,
                        book_id=chunk.book_id,
                        text_start=chunk.text_start,
                        text_end=chunk.text_end,
                        status=chunk.status,
                        chapter_id=chunk.chapter_id,
                        path=chunk.path,
                        generation_time_seconds=chunk.generation_time_seconds,
                        audio_duration_seconds=duration,
                        voice_name=chunk.voice_name,
                        speed=chunk.speed,
                        pre_pause_ms=chunk.pre_pause_ms,
                        post_pause_ms=chunk.post_pause_ms,
                        is_dialogue=chunk.is_dialogue,
                        is_scene_break=chunk.is_scene_break,
                    )
                    
                    # Save updated chunk
                    self.chunking_ctrl.sync.save_chunk(updated_chunk, chapter_number)
                    stats['chunks_updated'] += 1
                    logger.debug(f"Updated chunk {chunk.index} with duration {duration:.2f}s")
                else:
                    logger.warning(f"Invalid duration calculated for chunk {chunk.index}: {duration}")
                    stats['errors'] += 1
                    
            except Exception as e:
                logger.error(f"Error reading duration for chunk {chunk.index}: {e}", exc_info=True)
                stats['errors'] += 1
        
        logger.info(
            f"Backfill complete: {stats['chunks_updated']} updated, "
            f"{stats['chunks_already_had_duration']} already had duration, "
            f"{stats['chunks_missing_audio']} missing audio, "
            f"{stats['errors']} errors"
        )
        
        return stats
    
    def cleanup_small_failed_chunks(
        self,
        book_id: str,
        chapter_number: int,
    ) -> int:
        """
        Delete failed chunks that are purely whitespace.
        
        This is useful for cleaning up chunks created before the filtering logic
        was added, without having to rebuild all chunks.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Number of chunks deleted
        """
        logger.info(f"Cleaning up pure whitespace failed chunks for chapter: {book_id}/{chapter_number}")
        return self.chunking_ctrl.cleanup_small_failed_chunks(book_id, chapter_number)

