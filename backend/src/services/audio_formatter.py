"""Audio formatting service for converting and packaging audio files."""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChapterMarker:
    """Chapter marker metadata for audio files."""
    title: str
    start_time_ms: int  # Start time in milliseconds
    end_time_ms: int  # End time in milliseconds


class AudioFormatter:
    """Service for formatting audio files into various formats with metadata."""
    
    SUPPORTED_FORMATS = ['wav', 'm4b', 'm4a', 'mp3', 'flac', 'ogg']
    
    def __init__(self):
        """Initialize audio formatter."""
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("✅ FFmpeg is available")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        logger.warning("⚠️ FFmpeg not found. M4B/MP3/FLAC conversion will not be available.")
        logger.warning("   Install FFmpeg: https://ffmpeg.org/download.html")
        return False
    
    def convert_to_format(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str = 'm4b',
        bitrate: str = '128k',
        chapter_markers: Optional[List[ChapterMarker]] = None,
    ) -> Path:
        """
        Convert audio file to specified format with optional chapter markers.
        
        Args:
            input_path: Path to input audio file (WAV format)
            output_path: Path to output audio file
            output_format: Output format (m4b, m4a, mp3, flac, wav, ogg)
            bitrate: Audio bitrate (e.g., '128k', '192k', '256k')
            chapter_markers: Optional list of chapter markers
            
        Returns:
            Path to converted audio file
            
        Raises:
            ValueError: If format not supported or FFmpeg not available
            RuntimeError: If conversion fails
        """
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}. Supported: {self.SUPPORTED_FORMATS}")
        
        if not input_path.exists():
            raise ValueError(f"Input file does not exist: {input_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # For WAV format, just copy (no conversion needed)
        if output_format == 'wav':
            import shutil
            shutil.copy2(input_path, output_path)
            logger.info(f"✅ Copied WAV file to {output_path}")
            return output_path
        
        # Check FFmpeg availability for other formats
        if not self._check_ffmpeg():
            raise RuntimeError("FFmpeg is required for non-WAV formats but is not available")
        
        # Determine codec and container based on format
        codec_map = {
            'm4b': ('aac', 'ipod'),  # M4B uses AAC codec
            'm4a': ('aac', 'ipod'),
            'mp3': ('libmp3lame', None),
            'flac': ('flac', None),
            'ogg': ('libvorbis', None),
        }
        
        codec, container = codec_map.get(output_format, ('aac', 'ipod'))
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-codec:a', codec,
            '-b:a', bitrate,
            '-y',  # Overwrite output file
        ]
        
        # Add container format if specified
        if container:
            cmd.extend(['-f', container])
        
        # Add chapter metadata if provided
        if chapter_markers:
            chapter_file = self._generate_chapter_metadata(chapter_markers, output_path.parent)
            cmd.extend(['-i', str(chapter_file)])
            cmd.extend(['-map_metadata', '1'])
        
        cmd.append(str(output_path))
        
        # Run FFmpeg conversion
        try:
            logger.info(f"Converting {input_path.name} to {output_format} format...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            logger.info(f"✅ Converted to {output_format}: {output_path}")
            
            # Clean up temporary chapter file if created
            if chapter_markers:
                chapter_file.unlink(missing_ok=True)
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            error_msg = f"FFmpeg conversion failed: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired:
            error_msg = "FFmpeg conversion timed out"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def _generate_chapter_metadata(
        self,
        chapter_markers: List[ChapterMarker],
        output_dir: Path,
    ) -> Path:
        """
        Generate FFmpeg chapter metadata file.
        
        Args:
            chapter_markers: List of chapter markers
            output_dir: Directory to save metadata file
            
        Returns:
            Path to generated metadata file
        """
        metadata_file = output_dir / "chapters.txt"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            for i, chapter in enumerate(chapter_markers, start=1):
                f.write(f"[CHAPTER]\n")
                f.write(f"TIMEBASE=1/1000\n")
                f.write(f"START={chapter.start_time_ms}\n")
                f.write(f"END={chapter.end_time_ms}\n")
                f.write(f"title={chapter.title}\n")
                f.write("\n")
        
        logger.debug(f"Generated chapter metadata: {metadata_file}")
        return metadata_file
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """
        Get duration of audio file in seconds using FFprobe.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        if not self._check_ffmpeg():
            logger.warning("FFprobe not available, cannot get audio duration")
            return 0.0
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            duration = float(result.stdout.strip())
            return duration
            
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return 0.0
