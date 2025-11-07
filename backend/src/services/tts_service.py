"""Service for generating TTS audio from chunks."""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.tts.engine import get_tts_engine
from src.tts.voice_registry import load_voice_registry, Voice
from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker
from src.services.chunking_service import ChunkingService

logger = logging.getLogger(__name__)


class TTSChunkService:
    """Service for generating TTS audio from text chunks."""
    
    def __init__(self):
        """Initialize TTS chunk service."""
        self.settings = get_settings()
        self.engine = get_tts_engine()
        self.voice_registry = load_voice_registry()
        self.chunking_service = ChunkingService()
        # Get default voice from registry (narrator or first available)
        self._default_speaker = self.voice_registry.get('narrator') or (
            list(self.voice_registry.values())[0] if self.voice_registry else None
        )
    
    def find_book_dir(self, book_id: str) -> Optional[Path]:
        """
        Find book directory by book_id.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Path to book directory or None if not found
        """
        return self.chunking_service.find_book_dir(book_id)
    
    def generate_chunk_audio(
        self,
        book_id: str,
        chapter_title: str,
        chunk_index: int,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate audio for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_title: Chapter title
            chunk_index: Chunk index (1-based)
            speaker: Optional speaker WAV file path
            language: Optional language code
            speed: Optional playback speed
            emotion: Optional emotion parameter
            
        Returns:
            Dictionary with generation results
        """
        logger.info(f"Generating audio for chunk: {book_id}/{chapter_title}/chunk_{chunk_index}")
        
        # Find book directory
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        # Get chunk text
        chunk_text = self.chunking_service.get_chunk_text(book_id, chapter_title, chunk_index)
        if not chunk_text:
            raise ValueError(f"Chunk {chunk_index} not found for chapter {chapter_title}")
        
        # Get chunk metadata
        tracker = MetadataTracker(book_dir)
        metadata = tracker.load()
        chapter_meta = next(
            (ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title),
            None
        )
        
        if not chapter_meta:
            raise ValueError(f"Chapter {chapter_title} not found")
        
        chunk_metadata_list = chapter_meta.get('chunk_metadata', [])
        chunk_meta = next(
            (ch for ch in chunk_metadata_list if ch.get('index') == chunk_index),
            None
        )
        
        if not chunk_meta:
            raise ValueError(f"Chunk {chunk_index} metadata not found")
        
        # Check if chunk already has audio
        chapters_dir = book_dir / "chapters"
        chunk_filename = f"{chapter_title}_chunk_{chunk_index:03d}.wav"
        chunk_path = chapters_dir / chunk_filename
        
        if chunk_path.exists():
            logger.info(f"Chunk {chunk_index} already has audio, skipping")
            return {
                'chunk_index': chunk_index,
                'status': 'completed',
                'path': str(chunk_path),
                'skipped': True,
            }
        
        # Update chunk status to running
        chunk_meta['status'] = 'running'
        tracker.update_chunk_metadata(chapter_title, chunk_metadata_list)
        
        # Load model if not already loaded
        if not self.engine.is_loaded():
            logger.info("Loading TTS model...")
            self.engine.load_model()
        
        # Use default speaker if none provided
        if speaker is None and self._default_speaker:
            speaker = self._default_speaker.speaker_wav
            logger.info(f"Using default speaker: {self._default_speaker.name}")
        
        # Generate audio
        try:
            start_time = time.time()
            
            audio_path = self.engine.synthesize(
                text=chunk_text,
                output_path=chunk_path,
                annotations=None,
                speaker=speaker,
                language=language or self.settings.tts_language,
                speed=speed or self.settings.tts_speed,
                emotion=emotion or self.settings.tts_emotion,
            )
            
            generation_time = time.time() - start_time
            
            # Update chunk metadata
            chunk_meta['status'] = 'completed'
            chunk_meta['generation_time_seconds'] = generation_time
            chunk_meta['path'] = str(audio_path)
            tracker.update_chunk_metadata(chapter_title, chunk_metadata_list)
            
            # Update chapter audio status
            tracker.mark_chapter_audio_generated(chapter_title)
            
            logger.info(f"✅ Generated audio for chunk {chunk_index}: {audio_path}")
            
            return {
                'chunk_index': chunk_index,
                'status': 'completed',
                'path': str(audio_path),
                'generation_time_seconds': generation_time,
                'file_size_mb': audio_path.stat().st_size / (1024 * 1024),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate audio for chunk {chunk_index}: {e}")
            
            # Update chunk status to failed
            chunk_meta['status'] = 'failed'
            chunk_meta['error'] = str(e)
            tracker.update_chunk_metadata(chapter_title, chunk_metadata_list)
            
            raise
    
    def generate_chapter_chunks(
        self,
        book_id: str,
        chapter_title: str,
        chunk_indices: Optional[List[int]] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate audio for multiple chunks in a chapter.
        
        Args:
            book_id: Book identifier
            chapter_title: Chapter title
            chunk_indices: Optional list of chunk indices to generate (defaults to all pending chunks)
            speaker: Optional speaker WAV file path
            language: Optional language code
            speed: Optional playback speed
            emotion: Optional emotion parameter
            
        Returns:
            Dictionary with generation results
        """
        logger.info(f"Generating audio for chapter: {book_id}/{chapter_title}")
        
        # Get chunk metadata
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        tracker = MetadataTracker(book_dir)
        metadata = tracker.load()
        chapter_meta = next(
            (ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title),
            None
        )
        
        if not chapter_meta:
            raise ValueError(f"Chapter {chapter_title} not found")
        
        chunk_metadata_list = chapter_meta.get('chunk_metadata', [])
        
        if not chunk_metadata_list:
            raise ValueError(f"Chapter {chapter_title} has no chunks. Chunk the chapter first.")
        
        # Determine which chunks to generate
        if chunk_indices is None:
            # Generate all pending chunks
            chunk_indices = [
                ch['index'] for ch in chunk_metadata_list
                if ch.get('status') == 'pending'
            ]
        
        if not chunk_indices:
            logger.info("No chunks to generate")
            return {
                'chapter_title': chapter_title,
                'generated': 0,
                'skipped': 0,
                'failed': 0,
            }
        
        # Generate audio for each chunk
        results = {
            'chapter_title': chapter_title,
            'generated': 0,
            'skipped': 0,
            'failed': 0,
            'chunks': [],
        }
        
        for chunk_index in chunk_indices:
            try:
                result = self.generate_chunk_audio(
                    book_id=book_id,
                    chapter_title=chapter_title,
                    chunk_index=chunk_index,
                    speaker=speaker,
                    language=language,
                    speed=speed,
                    emotion=emotion,
                )
                results['chunks'].append(result)
                if result.get('skipped'):
                    results['skipped'] += 1
                else:
                    results['generated'] += 1
            except Exception as e:
                logger.error(f"Failed to generate chunk {chunk_index}: {e}")
                results['failed'] += 1
                results['chunks'].append({
                    'chunk_index': chunk_index,
                    'status': 'failed',
                    'error': str(e),
                })
        
        logger.info(f"✅ Generated {results['generated']} chunks, skipped {results['skipped']}, failed {results['failed']}")
        
        return results

