"""CLI script to generate audio for a chapter."""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tts.generator import AudioGenerator
from src.utils.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate audio for a chapter")
    parser.add_argument(
        "text_path",
        type=str,
        help="Path to text file (chapter)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output audio file path (defaults to same directory as text with .wav extension)",
    )
    parser.add_argument(
        "--speaker",
        type=str,
        help="Speaker reference audio file for XTTS v2 (optional)",
    )
    parser.add_argument(
        "--language",
        type=str,
        help="Language code (defaults to config value)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        help="Speech speed multiplier (0.5-2.0, defaults to config value)",
    )
    parser.add_argument(
        "--emotion",
        type=str,
        help="Emotion for XTTS v2 (neutral, happy, sad, angry, etc.)",
    )
    parser.add_argument(
        "--chunked",
        action="store_true",
        help="Generate chunked audio files (~1 minute each, at paragraph breaks)",
    )
    parser.add_argument(
        "--chunk-duration",
        type=float,
        default=1.0,
        help="Target duration per chunk in minutes (default: 1.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for chunked files (defaults to same directory as text)",
    )

    args = parser.parse_args()

    # Validate text path
    text_path = Path(args.text_path)
    if not text_path.exists():
        logger.error(f"Text file not found: {text_path}")
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = text_path.with_suffix(".wav")

    # Validate speaker path if provided
    speaker_path = None
    if args.speaker:
        speaker_path = Path(args.speaker)
        if not speaker_path.exists():
            logger.error(f"Speaker reference file not found: {speaker_path}")
            return 1

    # Validate speed if provided
    if args.speed is not None:
        if not 0.5 <= args.speed <= 2.0:
            logger.error("Speed must be between 0.5 and 2.0")
            return 1

    try:
        # Initialize generator
        generator = AudioGenerator()

        # Generate audio (chunked or single file)
        if args.chunked:
            logger.info(f"Generating chunked audio for: {text_path.name}")
            logger.info(f"Target duration per chunk: {args.chunk_duration} minutes")
            
            output_dir = Path(args.output_dir) if args.output_dir else None
            
            audio_files = generator.generate_chapter_chunked(
                text_path=text_path,
                output_dir=output_dir,
                chunk_duration_minutes=args.chunk_duration,
                speaker=str(speaker_path) if speaker_path else None,
                language=args.language,
                speed=args.speed,
                emotion=args.emotion,
            )
            
            total_size_mb = sum(f.stat().st_size for f in audio_files) / (1024 * 1024)
            logger.info(f"\n✅ Generated {len(audio_files)} audio chunks!")
            logger.info(f"   Total size: {total_size_mb:.2f} MB")
            logger.info(f"   Files:")
            for audio_file in audio_files:
                file_size_mb = audio_file.stat().st_size / (1024 * 1024)
                logger.info(f"     - {audio_file.name} ({file_size_mb:.2f} MB)")
        else:
            logger.info(f"Generating audio for: {text_path.name}")
            logger.info(f"Output: {output_path}")

            audio_path = generator.generate_chapter(
                text_path=text_path,
                output_path=output_path,
                speaker=str(speaker_path) if speaker_path else None,
                language=args.language,
                speed=args.speed,
                emotion=args.emotion,
            )

            # Get file size
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Audio generated successfully!")
            logger.info(f"   File: {audio_path}")
            logger.info(f"   Size: {file_size_mb:.2f} MB")

        return 0

    except Exception as e:
        logger.error(f"Failed to generate audio: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

