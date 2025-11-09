"""Service for concatenating audio chunks into a single file."""

import logging
import wave
from pathlib import Path
from typing import List, Optional

from src.services.audio_formatter import AudioFormatter, ChapterMarker
from src.utils.config import get_settings
from src.utils.file_operations import get_audio_duration

logger = logging.getLogger(__name__)


class AudioConcatenator:
    """Service for concatenating multiple audio files into one."""
    
    def __init__(self):
        """Initialize audio concatenator."""
        self.settings = get_settings()
        self.formatter = AudioFormatter()
    
    def concatenate_chunks(
        self,
        book_id: str,
        chapter_number: int,
        chunk_audio_paths: List[Path],
        output_path: Optional[Path] = None,
        output_format: Optional[str] = None,
        chapter_title: Optional[str] = None,
    ) -> Path:
        """
        Concatenate multiple audio chunk files into a single audio file.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_audio_paths: List of paths to chunk audio files (WAV format)
            output_path: Optional output path (defaults to chapter_dir/audio.{format})
            output_format: Optional output format (wav, m4b, m4a, mp3, flac, ogg). Defaults to config setting.
            chapter_title: Optional chapter title for chapter markers
            
        Returns:
            Path to the concatenated audio file
            
        Raises:
            ValueError: If no audio files provided or concatenation fails
        """
        if not chunk_audio_paths:
            raise ValueError("No audio files provided for concatenation")
        
        # Determine output format
        if output_format is None:
            output_format = self.settings.audio_output_format
        
        # Determine output path
        if output_path is None:
            # Default: chapter_dir/audio.{format}
            book_dir = self.settings.books_dir
            # Find book directory
            book_path = None
            for dir_path in book_dir.iterdir():
                if dir_path.is_dir() and book_id in dir_path.name:
                    book_path = dir_path
                    break
            
            if book_path is None:
                raise ValueError(f"Book directory not found for {book_id}")
            
            chapter_dir = book_path / "chapters" / f"{chapter_number:02d}"
            output_path = chapter_dir / f"audio.{output_format}"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Always create WAV first (for conversion), then convert if needed
        wav_output_path = output_path.parent / "audio.wav"
        if output_format == 'wav':
            wav_output_path = output_path
        
        # Check if output already exists and is newer than all chunks
        if output_path.exists():
            output_mtime = output_path.stat().st_mtime
            all_chunks_newer = all(
                path.exists() and path.stat().st_mtime <= output_mtime
                for path in chunk_audio_paths
            )
            if all_chunks_newer:
                logger.info(f"Concatenated audio already exists and is up-to-date: {output_path}")
                return output_path
        
        logger.info(f"Concatenating {len(chunk_audio_paths)} audio chunks into {wav_output_path}")
        
        # Read first file to get parameters
        first_file = None
        for path in chunk_audio_paths:
            if path.exists():
                first_file = path
                break
        
        if first_file is None:
            raise ValueError("No valid audio files found")
        
        with wave.open(str(first_file), 'rb') as first_wav:
            params = first_wav.getparams()
            n_channels, sampwidth, framerate, n_frames, comptype, compname = params
        
        # Concatenate all audio files
        total_frames = 0
        valid_paths = [p for p in chunk_audio_paths if p.exists()]
        
        if not valid_paths:
            raise ValueError("No valid audio files found")
        
        # Write concatenated file (always WAV first)
        with wave.open(str(wav_output_path), 'wb') as out_wav:
            out_wav.setparams(params)
            
            for i, audio_path in enumerate(valid_paths):
                try:
                    with wave.open(str(audio_path), 'rb') as in_wav:
                        # Verify parameters match
                        in_params = in_wav.getparams()
                        if in_params[:3] != params[:3]:  # Check channels, sampwidth, framerate
                            logger.warning(
                                f"Audio file {audio_path} has different parameters. "
                                f"Expected {params[:3]}, got {in_params[:3]}. "
                                "Attempting to continue..."
                            )
                        
                        # Read and write frames
                        frames = in_wav.readframes(in_wav.getnframes())
                        out_wav.writeframes(frames)
                        total_frames += in_wav.getnframes()
                        
                        logger.debug(f"Added chunk {i+1}/{len(valid_paths)}: {audio_path.name}")
                
                except Exception as e:
                    logger.error(f"Error processing chunk {audio_path}: {e}")
                    # Continue with next chunk
                    continue
        
        logger.info(f"✅ Concatenated {len(valid_paths)} chunks into WAV: {wav_output_path} ({total_frames} frames)")
        
        # If output format is not WAV, convert it
        if output_format != 'wav':
            # Generate chapter markers if enabled and we have chunk durations
            chapter_markers = None
            if self.settings.audio_generate_chapters and chunk_audio_paths:
                chapter_markers = self._generate_chapter_markers(
                    chunk_audio_paths,
                    chapter_title or f"Chapter {chapter_number}"
                )
            
            # Convert to requested format
            output_path = self.formatter.convert_to_format(
                input_path=wav_output_path,
                output_path=output_path,
                output_format=output_format,
                bitrate=self.settings.audio_bitrate,
                chapter_markers=chapter_markers,
            )
            
            # Remove temporary WAV file if we created a different format
            if wav_output_path != output_path:
                wav_output_path.unlink(missing_ok=True)
                logger.debug(f"Removed temporary WAV file: {wav_output_path}")
        else:
            # For WAV format, just rename if needed
            if wav_output_path != output_path:
                wav_output_path.rename(output_path)
        
        return output_path
    
    def _generate_chapter_markers(
        self,
        chunk_audio_paths: List[Path],
        chapter_title: str,
    ) -> List[ChapterMarker]:
        """
        Generate chapter markers from chunk audio files.
        
        Args:
            chunk_audio_paths: List of chunk audio file paths
            chapter_title: Title for the chapter
            
        Returns:
            List of chapter markers
        """
        markers = []
        current_time_ms = 0
        
        for i, chunk_path in enumerate(chunk_audio_paths, start=1):
            if not chunk_path.exists():
                continue
            
            # Get chunk duration
            duration = get_audio_duration(chunk_path)
            duration_ms = int(duration * 1000)
            
            if duration_ms > 0:
                start_ms = current_time_ms
                end_ms = current_time_ms + duration_ms
                
                # Use chunk index as marker title
                marker_title = f"{chapter_title} - Part {i}"
                markers.append(ChapterMarker(
                    title=marker_title,
                    start_time_ms=start_ms,
                    end_time_ms=end_ms,
                ))
                
                current_time_ms = end_ms
        
        return markers
    
    def get_concatenated_audio_path(
        self,
        book_id: str,
        chapter_number: int,
    ) -> Optional[Path]:
        """
        Get the path to the concatenated audio file for a chapter.
        Creates it if it doesn't exist and all chunks are available.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Path to concatenated audio file, or None if chunks not available
        """
        # Find book directory
        book_dir = self.settings.books_dir
        book_path = None
        for dir_path in book_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                book_path = dir_path
                break
        
        if book_path is None:
            return None
        
        chapter_dir = book_path / "chapters" / f"{chapter_number:02d}"
        chunks_dir = chapter_dir / "chunks"
        
        if not chunks_dir.exists():
            return None
        
        # Collect all chunk audio files
        chunk_audio_paths = []
        for chunk_dir in sorted(chunks_dir.iterdir(), key=lambda x: int(x.name) if x.name.isdigit() else 999):
            if chunk_dir.is_dir() and chunk_dir.name.isdigit():
                audio_file = chunk_dir / "audio.wav"
                if audio_file.exists():
                    chunk_audio_paths.append(audio_file)
        
        if not chunk_audio_paths:
            return None
        
        # Check if concatenated file already exists and is up-to-date
        output_format = self.settings.audio_output_format
        output_path = chapter_dir / f"audio.{output_format}"
        if output_path.exists():
            output_mtime = output_path.stat().st_mtime
            # Quick check: if output is newer than all chunks, return immediately
            all_chunks_newer = all(
                path.exists() and path.stat().st_mtime <= output_mtime
                for path in chunk_audio_paths
            )
            if all_chunks_newer:
                logger.debug(f"Concatenated audio exists and is up-to-date: {output_path}")
                return output_path
        
        # Only concatenate if file doesn't exist or is outdated
        try:
            return self.concatenate_chunks(
                book_id=book_id,
                chapter_number=chapter_number,
                chunk_audio_paths=chunk_audio_paths,
                output_path=output_path,
            )
        except Exception as e:
            logger.error(f"Failed to concatenate audio: {e}")
            return None

