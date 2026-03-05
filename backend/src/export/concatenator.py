"""Audio concatenation and export functionality."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from src.config import get_settings
from src.discovery import BookDiscovery, ChunkDiscovery
from src.utils import sanitize_filename

logger = logging.getLogger(__name__)


class AudioConcatenator:
    """Concatenate chunk audio files into chapter audio."""

    def __init__(self):
        """Initialize the concatenator."""
        self.settings = get_settings()
        self.chunk_discovery = ChunkDiscovery()
        self.book_discovery = BookDiscovery()

    def concatenate_chapter(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
    ) -> Optional[Path]:
        """
        Concatenate all chunk audio files for a chapter into a single WAV.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            chapter_number: Chapter number

        Returns:
            Path to concatenated audio file, or None if failed
        """
        chunks = self.chunk_discovery.list_chunks(fiction_id, book_number, chapter_number)

        if not chunks:
            logger.error(f"No chunks found for chapter {chapter_number}")
            return None

        # Get audio files in order
        audio_files = []
        for chunk in sorted(chunks, key=lambda c: c.index):
            if chunk.audio_path and chunk.audio_path.exists():
                audio_files.append(chunk.audio_path)
            else:
                logger.warning(f"Missing audio for chunk {chunk.index}")

        if not audio_files:
            logger.error("No audio files to concatenate")
            return None

        # Output path
        chapter_dir = (
            self.settings.books_dir
            / fiction_id
            / f"book_{book_number}"
            / "chapters"
            / f"chapter_{chapter_number}"
        )
        output_path = chapter_dir / "audio.wav"

        try:
            # Use scipy for WAV concatenation
            from scipy.io import wavfile
            import numpy as np

            # Read all audio files
            sample_rate = None
            audio_data = []

            for audio_file in audio_files:
                rate, data = wavfile.read(audio_file)
                if sample_rate is None:
                    sample_rate = rate
                elif rate != sample_rate:
                    logger.warning(f"Sample rate mismatch: {rate} vs {sample_rate}")
                audio_data.append(data)

            # Concatenate
            combined = np.concatenate(audio_data)

            # Write output
            wavfile.write(output_path, sample_rate, combined)

            logger.info(f"✅ Created chapter audio: {output_path}")
            return output_path

        except ImportError:
            logger.warning("scipy not available, falling back to ffmpeg")
            return self._concatenate_with_ffmpeg(audio_files, output_path)
        except Exception as e:
            logger.error(f"Concatenation failed: {e}")
            return None

    def _concatenate_with_ffmpeg(
        self,
        audio_files: list[Path],
        output_path: Path,
    ) -> Optional[Path]:
        """Concatenate using ffmpeg as fallback."""
        try:
            # Create concat list file
            concat_file = output_path.parent / "concat_list.txt"
            with open(concat_file, "w") as f:
                for audio_file in audio_files:
                    f.write(f"file '{audio_file}'\n")

            # Run ffmpeg
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            # Clean up
            concat_file.unlink()

            if result.returncode == 0:
                logger.info(f"✅ Created chapter audio: {output_path}")
                return output_path
            else:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"ffmpeg concatenation failed: {e}")
            return None


class AudioExporter:
    """Export audio files to final format."""

    def __init__(self):
        """Initialize the exporter."""
        self.settings = get_settings()
        self.concatenator = AudioConcatenator()
        self.book_discovery = BookDiscovery()

    def export_chapter(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
        format: str = "mp3",
    ) -> Optional[Path]:
        """
        Export a chapter to final audio format.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            chapter_number: Chapter number
            format: Output format (wav, m4b, mp3) - defaults to mp3 (audiobook-optimized)

        Returns:
            Path to exported file, or None if failed
        """
        # First concatenate if needed
        chapter_dir = (
            self.settings.books_dir
            / fiction_id
            / f"book_{book_number}"
            / "chapters"
            / f"chapter_{chapter_number}"
        )
        wav_path = chapter_dir / "audio.wav"

        if not wav_path.exists():
            wav_path = self.concatenator.concatenate_chapter(
                fiction_id, book_number, chapter_number
            )
            if not wav_path:
                return None

        # Get book info for naming
        book = self.book_discovery.get_book(fiction_id, book_number)
        if book:
            book_title = book.title
        else:
            book_title = f"Book {book_number}"

        # Create output filename
        output_name = f"{book_title} - Chapter {chapter_number}.{format}"
        output_name = self._sanitize_filename(output_name)

        # Ensure exports directory exists
        export_dir = self.settings.exports_dir / self._sanitize_filename(book_title)
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / output_name

        if format == "wav":
            # Just copy the WAV
            shutil.copy(wav_path, output_path)
            logger.info(f"✅ Exported: {output_path}")
            return output_path

        # Convert using ffmpeg
        return self._convert_audio(wav_path, output_path, format)

    def _convert_audio(
        self,
        input_path: Path,
        output_path: Path,
        format: str,
    ) -> Optional[Path]:
        """Convert audio to specified format using ffmpeg."""
        try:
            codec_args = []

            if format == "m4b":
                # AAC audio in M4B container (audiobook format)
                # Optimized for spoken word: mono, 48kbps AAC
                # -movflags +faststart is critical for proper seeking
                codec_args = [
                    "-ac", "1",  # Mono
                    "-c:a", "aac",
                    "-b:a", "48k",  # 48kbps is plenty for speech
                    "-movflags", "+faststart",
                ]
            elif format == "mp3":
                # Audiobook-optimized MP3:
                # - VBR quality 6 (~115kbps avg) - excellent for speech with variable complexity
                # - 22050 Hz sample rate - standard for audiobooks, half the file size
                # - Mono - speech doesn't need stereo
                codec_args = [
                    "-ac", "1",  # Mono
                    "-ar", "22050",  # 22.05 kHz sample rate (audiobook standard)
                    "-c:a", "libmp3lame",
                    "-q:a", "6",  # VBR quality 6 (~115kbps avg, range 5=~130kbps to 7=~100kbps)
                ]
            else:
                logger.error(f"Unknown format: {format}")
                return None

            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                *codec_args,
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(f"✅ Exported: {output_path}")
                return output_path
            else:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return None

    def _sanitize_filename(self, name: str) -> str:
        """Make a filename safe for filesystem use."""
        return sanitize_filename(name)

    def get_export_status(
        self,
        fiction_id: str,
        book_number: int,
    ) -> dict:
        """
        Get export status for all chapters in a book.

        Returns:
            Dictionary mapping chapter numbers to export status
        """
        book = self.book_discovery.get_book(fiction_id, book_number)
        if not book:
            return {}

        book_title = book.title
        export_dir = self.settings.exports_dir / self._sanitize_filename(book_title)

        status = {}
        for chapter_num in range(1, book.chapter_count + 1):
            for fmt in ["wav", "m4b", "mp3"]:
                filename = f"{book_title} - Chapter {chapter_num}.{fmt}"
                export_path = export_dir / self._sanitize_filename(filename)
                if export_path.exists():
                    status[chapter_num] = {
                        "exported": True,
                        "format": fmt,
                        "path": str(export_path),
                    }
                    break
            else:
                status[chapter_num] = {"exported": False}

        return status


# Convenience functions
def get_concatenator() -> AudioConcatenator:
    """Get concatenator instance."""
    return AudioConcatenator()


def get_exporter() -> AudioExporter:
    """Get exporter instance."""
    return AudioExporter()

