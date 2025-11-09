"""Controller for TTS audio generation operations."""

import logging
import time
import wave
from pathlib import Path
from typing import List, Optional

from src.data.db_repository import ChunkRepository
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import AudioGenerationResult, ChapterAudioGenerationResult
from src.tts.engine import get_tts_engine
from src.tts.voice_registry import load_voice_registry
from src.utils.config import get_settings
from src.utils.file_operations import save_chunk_metadata, get_chunk_text

logger = logging.getLogger(__name__)


class TTSController:
    """Controller for TTS audio generation operations."""
    
    def __init__(self):
        """Initialize TTS controller."""
        self.settings = get_settings()
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
        speed: Optional[float] = None,
    ) -> AudioGenerationResult:
        """
        Generate audio for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            speaker: Optional speaker WAV file path or voice name (overrides chunk metadata)
            speed: Optional playback speed (0.5-2.0, default 1.0)
            
        Returns:
            Dictionary with generation results
            
        Raises:
            ValueError: If book, chapter, or chunk not found
        """
        logger.info(f"Generating audio for chunk: {book_id}/{chapter_number}/chunk_{chunk_index}")
        
        # Load chunk from database
        chunk = ChunkRepository.get_by_book_chapter_index(book_id, chapter_number, chunk_index)
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
        
        # Get chunk text from filesystem
        chunk_text = get_chunk_text(chunk)
        if chunk_text is None:
            raise ValueError(f"Chunk {chunk_index} text file not found")
        
        # Update chunk status to running in database
        success = ChunkRepository.update_status(
            book_id, chapter_number, chunk_index, ChunkStatus.RUNNING
        )
        if not success:
            raise ValueError("Failed to update chunk status")
        
        # Load model if not already loaded
        if not self.engine.is_loaded():
            logger.info("Loading TTS model...")
            self.engine.load_model()
        
        # Speaker: Resolve voice_name from chunk via registry, or use parameter/default
        # Priority: chunk voice_name > speaker parameter (as voice name or path) > default
        resolved_speaker = None
        
        if chunk.voice_name:
            # Resolve voice name from registry
            voice = self.voice_registry.get(chunk.voice_name)
            if voice and voice.speaker_wav:
                resolved_speaker = voice.speaker_wav
                logger.info(f"Using voice from chunk: {chunk.voice_name}")
            else:
                logger.warning(f"Voice '{chunk.voice_name}' not found in registry")
        
        # If chunk didn't resolve, check speaker parameter
        if resolved_speaker is None and speaker:
            # Check if it's a voice name in the registry
            voice = self.voice_registry.get(speaker)
            if voice and voice.speaker_wav:
                resolved_speaker = voice.speaker_wav
                logger.info(f"Resolved speaker parameter as voice name: {voice.name}")
            else:
                # Check if it's a valid file path (backward compatibility)
                speaker_path = Path(speaker)
                if speaker_path.exists() and speaker_path.is_file():
                    resolved_speaker = speaker
                    logger.info(f"Using speaker parameter as file path: {speaker}")
                else:
                    # Not a valid voice name or file path - ignore and use default
                    logger.warning(
                        f"Speaker parameter '{speaker}' is not a valid voice name or file path. "
                        "Falling back to default voice."
                    )
        
        # Use default if no speaker resolved yet
        if resolved_speaker is None and self._default_speaker:
            resolved_speaker = self._default_speaker.speaker_wav
            logger.info(f"Using default speaker: {self._default_speaker.name}")
        
        speaker = resolved_speaker
        
        # Speed: chunk > parameter > settings
        synth_speed = speed
        if chunk.speed is not None:
            synth_speed = chunk.speed
        elif synth_speed is None:
            synth_speed = self.settings.tts_speed
        
        # Language is always English
        synth_language = "en"
        
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
                language=synth_language,
                speed=synth_speed,
            )
            
            generation_time = time.time() - start_time
            
            # Calculate audio duration from the generated WAV file
            audio_duration = None
            if generated_path and Path(generated_path).exists():
                from src.utils.file_operations import get_audio_duration
                audio_duration = get_audio_duration(Path(generated_path))
                if audio_duration:
                    logger.debug(f"Chunk {chunk_index} audio duration: {audio_duration:.2f}s")
                else:
                    logger.warning(f"Failed to read audio duration for chunk {chunk_index}")
            
            # Update chunk status to completed in database
            # Note: We need to update the chunk with generation_time_seconds and audio_duration_seconds
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
                audio_duration_seconds=audio_duration,
                voice_name=chunk.voice_name,
                speed=chunk.speed,
                pre_pause_ms=chunk.pre_pause_ms,
                post_pause_ms=chunk.post_pause_ms,
                is_dialogue=chunk.is_dialogue,
                is_scene_break=chunk.is_scene_break,
            )
            # Save to database and filesystem
            ChunkRepository.create_or_update(completed_chunk, chapter_number)
            save_chunk_metadata(completed_chunk)
            
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
            
            # Update chunk status to failed in database
            ChunkRepository.update_status(
                book_id, chapter_number, chunk_index, ChunkStatus.FAILED, error=str(e)
            )
            # Update metadata file on filesystem
            failed_chunk = ChunkRepository.get_by_book_chapter_index(book_id, chapter_number, chunk_index)
            if failed_chunk:
                save_chunk_metadata(failed_chunk)
            
            raise
    
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
            speaker: Optional speaker WAV file path or voice name (overrides chunk metadata)
            speed: Optional playback speed (0.5-2.0, default 1.0)
            
        Returns:
            Dictionary with generation results
            
        Raises:
            ValueError: If book or chapter not found
        """
        logger.info(f"Generating audio for chapter: {book_id}/{chapter_number}")
        
        # Load chunks from database
        chunks = ChunkRepository.get_by_chapter(book_id, chapter_number)
        
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
                    speed=speed,
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

