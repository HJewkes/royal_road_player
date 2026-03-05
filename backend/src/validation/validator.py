"""Audio validation service - validates TTS output against source text."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import get_settings
from src.discovery import ChunkDiscovery
from src.models import ChapterValidationResult, ChunkValidationResult
from src.validation.comparison import compare_texts, ComparisonResult
from src.validation.stt import get_stt_service

logger = logging.getLogger(__name__)


class AudioValidator:
    """Validates TTS audio output against source text using STT."""

    def __init__(self):
        """Initialize the validator."""
        self.settings = get_settings()
        self.stt = get_stt_service()
        self.chunk_discovery = ChunkDiscovery()
        self.threshold = self.settings.validation_threshold

    def validate_chunk(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
        chunk_index: int,
    ) -> Optional[ChunkValidationResult]:
        """
        Validate a single chunk by comparing TTS audio to source text.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            chapter_number: Chapter number
            chunk_index: Chunk index

        Returns:
            ChunkValidationResult or None if validation fails
        """
        chunk = self.chunk_discovery.get_chunk(
            fiction_id, book_number, chapter_number, chunk_index
        )

        if chunk is None:
            logger.error(f"Chunk not found: {fiction_id}/{book_number}/{chapter_number}/{chunk_index}")
            return None

        if not chunk.audio_path or not chunk.audio_path.exists():
            logger.error(f"Audio file not found for chunk {chunk_index}")
            return None

        # Transcribe audio
        transcribed = self.stt.transcribe(chunk.audio_path)

        if transcribed is None:
            return ChunkValidationResult(
                chunk_index=chunk_index,
                similarity=0.0,
                passed=False,
                issues=["Transcription failed"],
            )

        # Compare texts
        result = compare_texts(chunk.text, transcribed, self.threshold)

        return ChunkValidationResult(
            chunk_index=chunk_index,
            similarity=result.similarity,
            passed=result.passed,
            issues=result.issues,
            expected_text=chunk.text,
            transcribed_text=transcribed,
        )

    def validate_chapter(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
    ) -> Optional[ChapterValidationResult]:
        """
        Validate all chunks in a chapter.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            chapter_number: Chapter number

        Returns:
            ChapterValidationResult with all chunk results
        """
        chunks = self.chunk_discovery.list_chunks(fiction_id, book_number, chapter_number)

        if not chunks:
            logger.error(f"No chunks found for chapter {chapter_number}")
            return None

        chunk_results = {}
        passed_count = 0
        failed_count = 0

        for chunk in chunks:
            if not chunk.has_audio:
                logger.warning(f"Skipping chunk {chunk.index}: no audio")
                continue

            result = self.validate_chunk(
                fiction_id, book_number, chapter_number, chunk.index
            )

            if result:
                chunk_results[f"{chunk.index:03d}"] = result
                if result.passed:
                    passed_count += 1
                else:
                    failed_count += 1

        if not chunk_results:
            return None

        chapter_result = ChapterValidationResult(
            chapter_number=chapter_number,
            validated_at=datetime.utcnow(),
            total_chunks=len(chunk_results),
            passed_chunks=passed_count,
            failed_chunks=failed_count,
            chunks=chunk_results,
        )

        # Save validation results to filesystem
        self._save_validation_result(
            fiction_id, book_number, chapter_number, chapter_result
        )

        return chapter_result

    def _save_validation_result(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
        result: ChapterValidationResult,
    ) -> None:
        """Save validation result to chapter directory."""
        chapter_dir = (
            self.settings.books_dir
            / fiction_id
            / f"book_{book_number}"
            / "chapters"
            / f"chapter_{chapter_number}"
        )

        if not chapter_dir.exists():
            logger.warning(f"Chapter directory not found: {chapter_dir}")
            return

        validation_path = chapter_dir / "validation.json"

        try:
            with open(validation_path, "w") as f:
                json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
            logger.info(f"Saved validation results to {validation_path}")
        except Exception as e:
            logger.error(f"Failed to save validation results: {e}")

    def get_validation_result(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
    ) -> Optional[ChapterValidationResult]:
        """Load saved validation result from filesystem."""
        chapter_dir = (
            self.settings.books_dir
            / fiction_id
            / f"book_{book_number}"
            / "chapters"
            / f"chapter_{chapter_number}"
        )

        validation_path = chapter_dir / "validation.json"

        if not validation_path.exists():
            return None

        try:
            with open(validation_path) as f:
                data = json.load(f)

            # Reconstruct chunk results
            chunk_results = {}
            for key, chunk_data in data.get("chunks", {}).items():
                chunk_results[key] = ChunkValidationResult(**chunk_data)

            return ChapterValidationResult(
                chapter_number=data["chapter_number"],
                validated_at=datetime.fromisoformat(data["validated_at"]),
                total_chunks=data["total_chunks"],
                passed_chunks=data["passed_chunks"],
                failed_chunks=data["failed_chunks"],
                chunks=chunk_results,
            )
        except Exception as e:
            logger.error(f"Failed to load validation results: {e}")
            return None


# Singleton instance
_validator: Optional[AudioValidator] = None


def get_audio_validator() -> AudioValidator:
    """Get audio validator singleton."""
    global _validator
    if _validator is None:
        _validator = AudioValidator()
    return _validator


