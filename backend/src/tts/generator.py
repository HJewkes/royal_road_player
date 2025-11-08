"""Audio generation pipeline.

DEPRECATED: This class is deprecated and will be removed in a future version.
Use TTSController instead, which works with the new nested structure and controller architecture.

Legacy code paths (jobs.py) still use this class for backward compatibility with the old flat structure.
"""

import json
import logging
import warnings
from pathlib import Path
from typing import List, Optional

from src.tts.engine import get_tts_engine
from src.tts.voice_registry import load_voice_registry, resolve_voice, Voice
from src.tts.dsl_parser import parse_dsl, Event
from src.tts.dsl_mapper import map_dsl_to_segments
from src.tts.segmenter import Segment
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class AudioGenerator:
    """
    Generate audio from text files.
    
    DEPRECATED: Use TTSController instead. This class works with the old flat structure
    (chapters/{chapter_title}.txt) and will be removed once jobs are migrated.
    """

    def __init__(self):
        """Initialize audio generator."""
        warnings.warn(
            "AudioGenerator is deprecated. Use TTSController instead. "
            "See docs/ARCHITECTURE_CONTROLLERS.md for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )
        self.settings = get_settings()
        self.engine = get_tts_engine()
        
        # For XTTS v2, use default speaker from config if available
        if hasattr(self.settings, 'tts_speaker') and self.settings.tts_speaker:
            # Check if it's a valid path
            speaker_path = Path(self.settings.tts_speaker)
            if speaker_path.exists():
                # Store as default for XTTS v2
                self._default_speaker = str(speaker_path.absolute())
            else:
                self._default_speaker = None
        else:
            self._default_speaker = None

    def generate_chapter(
        self,
        text_path: Path,
        output_path: Optional[Path] = None,
        annotation_path: Optional[Path] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> Path:
        """
        Generate audio for a chapter.

        Args:
            text_path: Path to text file
            output_path: Path to save audio (defaults to same directory as text with .wav extension)
            annotation_path: Optional path to annotation JSON file (not yet implemented)
            speaker: Speaker reference for XTTS v2 (overrides config)
            language: Language code (overrides config)
            speed: Speech speed multiplier (overrides config)
            emotion: Emotion for XTTS v2 (overrides config)

        Returns:
            Path to generated audio file
        """
        if not text_path.exists():
            raise FileNotFoundError(f"Text file not found: {text_path}")

        # Determine output path
        if output_path is None:
            output_path = text_path.with_suffix(".wav")
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Load text
        logger.info(f"Reading text from: {text_path}")
        text = text_path.read_text(encoding="utf-8")
        
        # Preprocess text for optimal XTTS v2 generation
        from src.tts.text_preprocessor import prepare_text_for_xtts, validate_text_for_xtts
        
        is_valid, warnings = validate_text_for_xtts(text)
        if warnings:
            logger.info(f"Text validation warnings: {', '.join(warnings)}")
        
        # Prepare text (normalize whitespace, preserve structure)
        text = prepare_text_for_xtts(text, preserve_structure=True)
        logger.debug(f"Text preprocessed: {len(text)} characters")

        # Load annotations if provided (future feature)
        annotations = None
        if annotation_path and annotation_path.exists():
            logger.info(f"Loading annotations from: {annotation_path}")
            with open(annotation_path, "r", encoding="utf-8") as f:
                annotations = json.load(f)

        # Load model if not already loaded
        if not self.engine.is_loaded():
            logger.info("Loading TTS model...")
            self.engine.load_model()

        # Generate audio
        logger.info(f"Generating audio: {output_path}")
        
        # Use default speaker if none provided and we have one
        if speaker is None and self._default_speaker:
            speaker = self._default_speaker
            logger.info(f"Using default speaker: {speaker}")
        
        audio_path = self.engine.synthesize(
            text=text,
            output_path=output_path,
            annotations=annotations,
            speaker=speaker,
            language=language,
            speed=speed,
            emotion=emotion,
        )

        logger.info(f"✅ Audio generated successfully: {audio_path}")
        
        # Note: Metadata is now handled by TTSController
        # This legacy generator is deprecated in favor of TTSController
        
        return audio_path

    def generate_chapter_chunked(
        self,
        text_path: Path,
        output_dir: Optional[Path] = None,
        chunk_duration_minutes: float = 1.0,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
        voice_registry_path: Optional[Path] = None,
        chapter_title: Optional[str] = None,
        text_offset: int = 0,
    ) -> List[Path]:
        """
        Generate audio for a chapter, chunked into multiple files (~1 minute each).
        
        Chunks are created at paragraph boundaries to ensure natural breaks.
        
        Args:
            text_path: Path to text file
            output_dir: Directory to save chunked audio files (defaults to same directory as text)
            chunk_duration_minutes: Target duration per chunk in minutes (default: 1.0)
            speaker: Speaker reference for XTTS v2 (overrides config)
            language: Language code (overrides config)
            speed: Speech speed multiplier (overrides config)
            emotion: Emotion for XTTS v2 (overrides config)
            
        Returns:
            List of paths to generated audio files (in order)
        """
        if not text_path.exists():
            raise FileNotFoundError(f"Text file not found: {text_path}")
        
        # Determine output directory
        if output_dir is None:
            output_dir = text_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and preprocess text
        logger.info(f"Reading text from: {text_path}")
        text = text_path.read_text(encoding="utf-8")
        
        from src.tts.text_preprocessor import prepare_text_for_xtts, validate_text_for_xtts
        
        is_valid, warnings = validate_text_for_xtts(text)
        if warnings:
            logger.info(f"Text validation warnings: {', '.join(warnings)}")
        
        text = prepare_text_for_xtts(text, preserve_structure=True)
        logger.info(f"Text preprocessed: {len(text)} characters")
        
        # Load voice registry
        voice_registry = load_voice_registry(voice_registry_path)
        default_voice = voice_registry.get('narrator') or (list(voice_registry.values())[0] if voice_registry else None)
        
        # Parse DSL if present (prototype)
        use_dsl = '[voice=' in text or '[pause:' in text or '[slow]' in text or '[fast]' in text or '[epigraph]' in text or '[scene-break]' in text
        
        if use_dsl:
            logger.info("DSL tags detected, parsing...")
            dsl_output = parse_dsl(text)
            # Map DSL to segments with voice assignments
            mapped_items = map_dsl_to_segments(dsl_output, voice_registry, default_voice)
            
            # Extract segments (skip events for now, they'll be handled in stitching phase)
            segments = [item for item in mapped_items if isinstance(item, Segment)]
            events = [item for item in mapped_items if isinstance(item, Event)]
            
            logger.info(f"Parsed {len(segments)} segments and {len(events)} events from DSL")
            
            # Convert segments to paragraphs for chunking
            paragraphs = [seg.text for seg in segments]
        else:
            # No DSL - pass text as-is to chunker (no preprocessing)
            text_for_chunking = text
        
        # Use provided speaker or default from registry
        if speaker is None and default_voice:
            speaker = default_voice.speaker_wav
            logger.info(f"Using default voice from registry: {default_voice.name}")
        
        # Chunk paragraphs targeting ~1 minute per chunk
        # IMPORTANT: XTTS v2 has a hard limit of 250 characters per synthesis call
        # This is much stricter than the token limit - we must respect this!
        # Estimate: ~200 chars ≈ 10-15 seconds of audio (conservative for 250 char limit)
        # For 1 minute, we'd need ~800 chars, but we'll chunk smaller to be safe
        target_chars = int(chunk_duration_minutes * 800)  # Reduced from 2000
        min_chars = int(target_chars * 0.3)  # At least 30% of target
        max_chars = min(int(target_chars * 1.5), 250)  # CRITICAL: Cap at 250 chars for XTTS v2
        
        from src.tts.chunker import chunk_text_by_paragraphs
        
        logger.info(f"Chunking text into ~{chunk_duration_minutes} minute segments...")
        # Pass text directly to chunker - no preprocessing, preserve all formatting
        chunk_data = chunk_text_by_paragraphs(
            text_for_chunking,
            target_chars_per_minute=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
            return_positions=True,
        )
        
        # Extract chunks and positions
        text_chunks = [chunk[0] if isinstance(chunk, tuple) else chunk for chunk in chunk_data]
        chunk_positions = [(chunk[1], chunk[2]) if isinstance(chunk, tuple) else (0, len(chunk)) for chunk in chunk_data]
        
        logger.info(f"Created {len(text_chunks)} chunks")
        for i, (chunk, (start_pos, end_pos)) in enumerate(zip(text_chunks, chunk_positions), 1):
            logger.debug(f"  Chunk {i}: {len(chunk)} characters (pos {start_pos}-{end_pos})")
        
        # Load model if not already loaded
        if not self.engine.is_loaded():
            logger.info("Loading TTS model...")
            self.engine.load_model()
        
        # Use default speaker if none provided
        if speaker is None and self._default_speaker:
            speaker = self._default_speaker
            logger.info(f"Using default speaker: {speaker}")
        
        # Check for existing chunks and only generate missing ones
        base_name = text_path.stem
        existing_chunks = {}
        existing_chunk_files = sorted(output_dir.glob(f"{base_name}_chunk_*.wav"))
        
        for chunk_file in existing_chunk_files:
            # Extract chunk number from filename
            chunk_num_str = chunk_file.stem.rsplit('_chunk_', 1)[-1]
            try:
                chunk_num = int(chunk_num_str)
                existing_chunks[chunk_num] = chunk_file
            except ValueError:
                continue
        
        logger.info(f"Found {len(existing_chunks)} existing chunks out of {len(text_chunks)} total")
        
        # Generate audio for each chunk (skip existing ones)
        audio_files = []
        skipped_count = 0
        import time
        chunk_metadata = []  # Store metadata for each chunk
        
        for i, (chunk_text, (start_pos, end_pos)) in enumerate(zip(text_chunks, chunk_positions), 1):
            chunk_num = f"{i:03d}"  # 001, 002, 003, etc.
            output_path = output_dir / f"{base_name}_chunk_{chunk_num}.wav"
            
            # Check if chunk already exists
            if i in existing_chunks:
                logger.info(f"Skipping chunk {i}/{len(text_chunks)} (already exists): {output_path.name}")
                audio_files.append(existing_chunks[i])
                skipped_count += 1
                # Load existing metadata if available
                chunk_metadata.append({
                    'index': i,
                    'text_start': start_pos,
                    'text_end': end_pos,
                    'text_length': len(chunk_text),
                    'status': 'completed',
                })
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Generating chunk {i}/{len(text_chunks)}: {output_path.name}")
            logger.info(f"Chunk size: {len(chunk_text)} characters (text pos {start_pos}-{end_pos})")
            
            try:
                start_time = time.time()
                audio_path = self.engine.synthesize(
                    text=chunk_text,
                    output_path=output_path,
                    annotations=None,
                    speaker=speaker,
                    language=language or self.settings.tts_language,
                    speed=speed or self.settings.tts_speed,
                    emotion=emotion or self.settings.tts_emotion,
                )
                generation_time = time.time() - start_time
                
                file_size_mb = audio_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Chunk {i} generated: {file_size_mb:.2f} MB in {generation_time:.1f}s")
                audio_files.append(audio_path)
                
                # Store chunk metadata
                chunk_metadata.append({
                    'index': i,
                    'text_start': start_pos,
                    'text_end': end_pos,
                    'text_length': len(chunk_text),
                    'generation_time_seconds': generation_time,
                    'status': 'completed',
                    'created_at': time.time(),
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to generate chunk {i}: {e}")
                # Store failed chunk metadata
                chunk_metadata.append({
                    'index': i,
                    'text_start': start_pos,
                    'text_end': end_pos,
                    'text_length': len(chunk_text),
                    'status': 'failed',
                })
                raise
        
        logger.info(f"\n{'='*60}")
        if skipped_count > 0:
            logger.info(f"✅ Processed {len(audio_files)} chunks ({skipped_count} skipped, {len(audio_files) - skipped_count} generated)")
        else:
            logger.info(f"✅ Generated {len(audio_files)} audio chunks")
        logger.info(f"   Output directory: {output_dir}")
        
        # Adjust chunk end positions to eliminate gaps between chunks
        # This prevents gaps in the coverage visualization by extending each chunk
        # to the start of the next chunk, accounting for whitespace and formatting
        for i in range(len(chunk_metadata) - 1):
            current_chunk = chunk_metadata[i]
            next_chunk = chunk_metadata[i + 1]
            current_end = current_chunk.get('text_end', 0)
            next_start = next_chunk.get('text_start', 0)
            
            # If there's a gap, extend current chunk's end to eliminate it
            # This accounts for whitespace, formatting, and any position tracking inaccuracies
            if current_end < next_start:
                current_chunk['text_end'] = next_start
                # Update text_length to reflect the extended coverage
                current_chunk['text_length'] = next_start - current_chunk.get('text_start', 0)
        
        # Note: Metadata is now handled by TTSController automatically
        # This legacy generator is deprecated in favor of TTSController
        # Chunk metadata is saved via ChunkController.save_chunk() in the new architecture
        
        return audio_files

    def generate_book(self, book_id: str) -> dict:
        """
        Generate audio for all chapters in a book.

        Args:
            book_id: Book identifier

        Returns:
            Dictionary with generation results
        """
        # TODO: Implement batch generation
        raise NotImplementedError("Batch generation not yet implemented")
