"""Filesystem-based discovery for books, chapters, and chunks.

All state is derived from the filesystem structure:
- data/books/{fiction_id}/book_{N}/
  - metadata.json
  - chapters/
    - chapter_{N}/
      - metadata.json
      - raw.txt (downloaded)
      - normalized.txt (normalized)
      - chunks/
        - 001.txt, 001.wav (chunk text and audio)
      - validation.json (validation results)
      - audio.wav (concatenated chapter audio)
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import get_settings
from src.models import (
    Book,
    BookMetadata,
    BookSummary,
    Chapter,
    ChapterMetadata,
    ChapterSummary,
    ChapterValidationResult,
    Chunk,
    ChunkStatus,
    ValidationStatus,
)
from src.utils import sanitize_filename

logger = logging.getLogger(__name__)


class BookDiscovery:
    """Discover and load books from the filesystem."""

    def __init__(self, books_dir: Optional[Path] = None):
        """Initialize with books directory."""
        self.books_dir = books_dir or get_settings().books_dir
        self.books_dir.mkdir(parents=True, exist_ok=True)

    def list_fictions(self) -> list[str]:
        """List all fiction IDs in the books directory."""
        if not self.books_dir.exists():
            return []

        return sorted([
            d.name for d in self.books_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    def list_books(self, fiction_id: str) -> list[BookSummary]:
        """List all books for a fiction ID."""
        fiction_dir = self.books_dir / fiction_id
        if not fiction_dir.exists():
            return []

        books = []
        for book_dir in sorted(fiction_dir.iterdir()):
            if not book_dir.is_dir() or not book_dir.name.startswith("book_"):
                continue

            try:
                book = self.get_book(fiction_id, int(book_dir.name.replace("book_", "")))
                if book:
                    books.append(BookSummary(
                        fiction_id=book.fiction_id,
                        book_number=book.book_number,
                        title=book.title,
                        status=book.status,
                        progress_percent=book.progress_percent,
                        chapter_count=book.chapter_count,
                        chapters_complete=book.chapters_audio_complete,
                        chapters_normalized=book.chapters_normalized,
                        chapters_chunked=book.chapters_chunked,
                    ))
            except Exception as e:
                logger.warning(f"Error loading book {book_dir}: {e}")

        return books

    def get_book(self, fiction_id: str, book_number: int) -> Optional[Book]:
        """Load a book with all computed status from filesystem."""
        book_dir = self.books_dir / fiction_id / f"book_{book_number}"
        metadata_path = book_dir / "metadata.json"

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path) as f:
                data = json.load(f)

            metadata = BookMetadata(**data)

            # Count chapter statuses
            chapters_dir = book_dir / "chapters"
            chapters_downloaded = 0
            chapters_normalized = 0
            chapters_chunked = 0
            chapters_audio_complete = 0
            chapters_validated = 0
            chapters_exported = 0
            chapter_count = 0

            if chapters_dir.exists():
                for ch_dir in chapters_dir.iterdir():
                    if not ch_dir.is_dir() or not ch_dir.name.startswith("chapter_"):
                        continue

                    chapter_count += 1

                    if (ch_dir / "raw.txt").exists():
                        chapters_downloaded += 1
                    if (ch_dir / "normalized.txt").exists():
                        chapters_normalized += 1
                    if (ch_dir / "chunks").exists() and any((ch_dir / "chunks").glob("*.txt")):
                        chapters_chunked += 1

                    # Check if all chunks have audio
                    chunks_dir = ch_dir / "chunks"
                    if chunks_dir.exists():
                        txt_files = list(chunks_dir.glob("*.txt"))
                        wav_files = list(chunks_dir.glob("*.wav"))
                        if txt_files and len(wav_files) >= len(txt_files):
                            chapters_audio_complete += 1

                    if (ch_dir / "validation.json").exists():
                        chapters_validated += 1

                    # Check exports (simplified - would need exports_dir reference)
                    if (ch_dir / "audio.wav").exists():
                        chapters_exported += 1

            return Book(
                fiction_id=metadata.fiction_id,
                book_number=metadata.book_number,
                title=metadata.title,
                author=metadata.author,
                source_url=metadata.source_url,
                scraped_at=metadata.scraped_at,
                chapter_count=chapter_count or metadata.chapter_count,
                path=book_dir,
                chapters_downloaded=chapters_downloaded,
                chapters_normalized=chapters_normalized,
                chapters_chunked=chapters_chunked,
                chapters_audio_complete=chapters_audio_complete,
                chapters_validated=chapters_validated,
                chapters_exported=chapters_exported,
            )

        except Exception as e:
            logger.error(f"Error loading book {book_dir}: {e}")
            return None

    def get_book_path(self, fiction_id: str, book_number: int) -> Path:
        """Get path to a book directory."""
        return self.books_dir / fiction_id / f"book_{book_number}"

    def create_book(self, metadata: BookMetadata) -> Book:
        """Create a new book directory with metadata."""
        book_dir = self.get_book_path(metadata.fiction_id, metadata.book_number)
        book_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = book_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

        # Create chapters directory
        (book_dir / "chapters").mkdir(exist_ok=True)

        return Book(
            **metadata.model_dump(),
            path=book_dir,
        )


class ChapterDiscovery:
    """Discover and load chapters from the filesystem."""

    def __init__(self, books_dir: Optional[Path] = None, exports_dir: Optional[Path] = None):
        """Initialize with directories."""
        settings = get_settings()
        self.books_dir = books_dir or settings.books_dir
        self.exports_dir = exports_dir or settings.exports_dir

    def list_chapters(self, fiction_id: str, book_number: int) -> list[ChapterSummary]:
        """List all chapters for a book."""
        book_dir = self.books_dir / fiction_id / f"book_{book_number}"
        chapters_dir = book_dir / "chapters"

        if not chapters_dir.exists():
            return []

        chapters = []
        for ch_dir in sorted(chapters_dir.iterdir(), key=lambda x: self._extract_chapter_num(x.name)):
            if not ch_dir.is_dir() or not ch_dir.name.startswith("chapter_"):
                continue

            try:
                chapter = self.get_chapter(fiction_id, book_number, self._extract_chapter_num(ch_dir.name))
                if chapter:
                    chapters.append(ChapterSummary(
                        chapter_number=chapter.chapter_number,
                        title=chapter.title,
                        status=chapter.status,
                        progress_percent=chapter.progress_percent,
                        chunk_count=chapter.chunk_count,
                        chunks_completed=chapter.chunks_completed,
                        is_normalized=chapter.is_normalized,
                        is_chunked=chapter.is_chunked,
                        is_audio_complete=chapter.is_audio_complete,
                        is_exported=chapter.is_exported,
                    ))
            except Exception as e:
                logger.warning(f"Error loading chapter {ch_dir}: {e}")

        return chapters

    def _extract_chapter_num(self, dirname: str) -> int:
        """Extract chapter number from directory name."""
        try:
            return int(dirname.replace("chapter_", ""))
        except ValueError:
            return 0

    def get_chapter(self, fiction_id: str, book_number: int, chapter_number: int) -> Optional[Chapter]:
        """Load a chapter with all computed status from filesystem."""
        chapter_dir = self.books_dir / fiction_id / f"book_{book_number}" / "chapters" / f"chapter_{chapter_number}"
        metadata_path = chapter_dir / "metadata.json"

        if not chapter_dir.exists():
            return None

        # Load metadata if exists
        title = f"Chapter {chapter_number}"
        source_url = None
        scraped_at = None
        audio_duration_seconds = None
        completed_at = None
        export_path = None

        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    data = json.load(f)
                    meta = ChapterMetadata(**data)
                    title = meta.title
                    source_url = meta.source_url
                    scraped_at = meta.scraped_at
                    audio_duration_seconds = meta.audio_duration_seconds
                    completed_at = meta.completed_at
                    export_path = meta.export_path
            except Exception as e:
                logger.warning(f"Error loading chapter metadata {metadata_path}: {e}")

        # Check file existence for status
        is_downloaded = (chapter_dir / "raw.txt").exists()
        is_normalized = (chapter_dir / "normalized.txt").exists()

        chunks_dir = chapter_dir / "chunks"
        is_chunked = chunks_dir.exists() and any(chunks_dir.glob("*.txt"))

        # Count chunks
        chunk_count = 0
        chunks_completed = 0
        chunks_failed = 0

        if chunks_dir.exists():
            txt_files = sorted(chunks_dir.glob("*.txt"))
            chunk_count = len(txt_files)

            for txt_file in txt_files:
                wav_file = txt_file.with_suffix(".wav")
                if wav_file.exists():
                    chunks_completed += 1
                # Check for error files
                err_file = txt_file.with_suffix(".error")
                if err_file.exists():
                    chunks_failed += 1

        is_audio_complete = chunk_count > 0 and chunks_completed == chunk_count

        # Check validation
        is_validated = False
        validation_passed = None
        validation_path = chapter_dir / "validation.json"
        if validation_path.exists():
            is_validated = True
            try:
                with open(validation_path) as f:
                    val_data = json.load(f)
                    validation_passed = val_data.get("failed_chunks", 1) == 0
            except Exception:
                pass

        # Check export - the durable completion marker (metadata.completed_at)
        # is authoritative and survives pruning; fall back to the export file on
        # disk for chapters completed before the marker existed.
        is_exported = completed_at is not None or self._check_export_exists(
            fiction_id, book_number, chapter_number
        )

        return Chapter(
            chapter_number=chapter_number,
            title=title,
            source_url=source_url,
            scraped_at=scraped_at,
            chunk_count=chunk_count,
            audio_duration_seconds=audio_duration_seconds,
            completed_at=completed_at,
            export_path=export_path,
            path=chapter_dir,
            is_downloaded=is_downloaded,
            is_normalized=is_normalized,
            is_chunked=is_chunked,
            chunks_completed=chunks_completed,
            chunks_failed=chunks_failed,
            is_audio_complete=is_audio_complete,
            is_validated=is_validated,
            validation_passed=validation_passed,
            is_exported=is_exported,
        )

    def get_chapter_path(self, fiction_id: str, book_number: int, chapter_number: int) -> Path:
        """Get path to a chapter directory."""
        return self.books_dir / fiction_id / f"book_{book_number}" / "chapters" / f"chapter_{chapter_number}"

    def create_chapter(self, fiction_id: str, book_number: int, metadata: ChapterMetadata) -> Chapter:
        """Create a new chapter directory with metadata."""
        chapter_dir = self.get_chapter_path(fiction_id, book_number, metadata.chapter_number)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = chapter_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

        # Create chunks directory
        (chapter_dir / "chunks").mkdir(exist_ok=True)

        return Chapter(
            **metadata.model_dump(),
            path=chapter_dir,
        )

    def mark_chapter_completed(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
        export_path: Path,
    ) -> None:
        """Record a durable completion marker in the chapter's metadata.json.

        Written at export time. Because it lives in metadata.json — which
        disk-cleanup leaves in place — a completed chapter stays distinguishable
        from a genuinely interrupted one even after audio.wav and chunk wavs are
        pruned. Existing metadata fields are preserved (read-merge-write).
        """
        chapter_dir = self.get_chapter_path(fiction_id, book_number, chapter_number)
        metadata_path = chapter_dir / "metadata.json"

        data = {}
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"Error reading metadata to mark completed {metadata_path}: {e}")

        data.setdefault("chapter_number", chapter_number)
        data.setdefault("title", f"Chapter {chapter_number}")
        data["completed_at"] = datetime.now().isoformat()
        data["export_path"] = str(export_path)

        chapter_dir.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def is_chapter_completed(self, fiction_id: str, book_number: int, chapter_number: int) -> bool:
        """True if the chapter carries a durable completion marker.

        Survives pruning, so callers (partial-generation recovery, disk audits)
        can tell a finished-then-pruned chapter from one interrupted mid-TTS
        without trusting audio.wav to still be on disk.
        """
        metadata_path = self.get_chapter_path(fiction_id, book_number, chapter_number) / "metadata.json"
        if not metadata_path.exists():
            return False
        try:
            with open(metadata_path) as f:
                return json.load(f).get("completed_at") is not None
        except Exception:
            return False

    def save_raw_text(self, fiction_id: str, book_number: int, chapter_number: int, text: str):
        """Save raw scraped text for a chapter."""
        chapter_dir = self.get_chapter_path(fiction_id, book_number, chapter_number)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        raw_path = chapter_dir / "raw.txt"
        with open(raw_path, "w") as f:
            f.write(text)

    def save_normalized_text(self, fiction_id: str, book_number: int, chapter_number: int, text: str):
        """Save normalized text for a chapter."""
        chapter_dir = self.get_chapter_path(fiction_id, book_number, chapter_number)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        normalized_path = chapter_dir / "normalized.txt"
        with open(normalized_path, "w") as f:
            f.write(text)

    def get_raw_text(self, fiction_id: str, book_number: int, chapter_number: int) -> Optional[str]:
        """Get raw text for a chapter."""
        raw_path = self.get_chapter_path(fiction_id, book_number, chapter_number) / "raw.txt"
        if not raw_path.exists():
            return None
        with open(raw_path) as f:
            return f.read()

    def get_normalized_text(self, fiction_id: str, book_number: int, chapter_number: int) -> Optional[str]:
        """Get normalized text for a chapter."""
        normalized_path = self.get_chapter_path(fiction_id, book_number, chapter_number) / "normalized.txt"
        if not normalized_path.exists():
            return None
        with open(normalized_path) as f:
            return f.read()

    def _check_export_exists(self, fiction_id: str, book_number: int, chapter_number: int) -> bool:
        """Check if an export file exists for this chapter in the exports directory."""
        # Get book title from metadata
        book_dir = self.books_dir / fiction_id / f"book_{book_number}"
        metadata_path = book_dir / "metadata.json"

        if not metadata_path.exists():
            return False

        try:
            with open(metadata_path) as f:
                data = json.load(f)
                book_title = data.get("title", f"Book {book_number}")
        except Exception:
            book_title = f"Book {book_number}"

        sanitized_title = sanitize_filename(book_title)
        export_dir = self.exports_dir / sanitized_title

        if not export_dir.exists():
            return False

        # Check for any supported format
        for fmt in ["wav", "m4b", "mp3"]:
            filename = sanitize_filename(f"{book_title} - Chapter {chapter_number}.{fmt}")
            export_path = export_dir / filename
            if export_path.exists():
                return True

        return False


class ChunkDiscovery:
    """Discover and manage chunks from the filesystem."""

    def __init__(self, books_dir: Optional[Path] = None):
        """Initialize with books directory."""
        self.books_dir = books_dir or get_settings().books_dir

    def get_chunks_dir(self, fiction_id: str, book_number: int, chapter_number: int) -> Path:
        """Get path to chunks directory for a chapter."""
        return self.books_dir / fiction_id / f"book_{book_number}" / "chapters" / f"chapter_{chapter_number}" / "chunks"

    def list_chunks(self, fiction_id: str, book_number: int, chapter_number: int) -> list[Chunk]:
        """List all chunks for a chapter."""
        chunks_dir = self.get_chunks_dir(fiction_id, book_number, chapter_number)
        if not chunks_dir.exists():
            return []

        chunks = []
        for txt_file in sorted(chunks_dir.glob("*.txt")):
            try:
                index = int(txt_file.stem)
                with open(txt_file) as f:
                    text = f.read()

                wav_file = txt_file.with_suffix(".wav")
                err_file = txt_file.with_suffix(".error")

                # Determine status
                if wav_file.exists():
                    status = ChunkStatus.COMPLETED
                elif err_file.exists():
                    status = ChunkStatus.FAILED
                else:
                    status = ChunkStatus.PENDING

                # Read error if exists
                error = None
                if err_file.exists():
                    with open(err_file) as f:
                        error = f.read()

                chunks.append(Chunk(
                    index=index,
                    text=text,
                    text_start=0,  # Would need to track this
                    text_end=len(text),
                    text_path=txt_file,
                    audio_path=wav_file if wav_file.exists() else None,
                    status=status,
                    error=error,
                ))
            except Exception as e:
                logger.warning(f"Error loading chunk {txt_file}: {e}")

        return chunks

    def get_chunk(self, fiction_id: str, book_number: int, chapter_number: int, chunk_index: int) -> Optional[Chunk]:
        """Get a specific chunk."""
        chunks_dir = self.get_chunks_dir(fiction_id, book_number, chapter_number)
        txt_file = chunks_dir / f"{chunk_index:03d}.txt"

        if not txt_file.exists():
            return None

        with open(txt_file) as f:
            text = f.read()

        wav_file = txt_file.with_suffix(".wav")
        err_file = txt_file.with_suffix(".error")

        if wav_file.exists():
            status = ChunkStatus.COMPLETED
        elif err_file.exists():
            status = ChunkStatus.FAILED
        else:
            status = ChunkStatus.PENDING

        error = None
        if err_file.exists():
            with open(err_file) as f:
                error = f.read()

        return Chunk(
            index=chunk_index,
            text=text,
            text_start=0,
            text_end=len(text),
            text_path=txt_file,
            audio_path=wav_file if wav_file.exists() else None,
            status=status,
            error=error,
        )

    def save_chunks(self, fiction_id: str, book_number: int, chapter_number: int, chunks: list[tuple[int, str]]):
        """Save chunk text files. chunks is list of (index, text) tuples."""
        chunks_dir = self.get_chunks_dir(fiction_id, book_number, chapter_number)
        chunks_dir.mkdir(parents=True, exist_ok=True)

        for index, text in chunks:
            txt_file = chunks_dir / f"{index:03d}.txt"
            with open(txt_file, "w") as f:
                f.write(text)

    def mark_chunk_complete(self, fiction_id: str, book_number: int, chapter_number: int, chunk_index: int, audio_path: Path):
        """Mark a chunk as complete by ensuring audio file exists."""
        # Audio file should already be written by TTS engine
        # Just verify it exists
        chunks_dir = self.get_chunks_dir(fiction_id, book_number, chapter_number)
        expected_path = chunks_dir / f"{chunk_index:03d}.wav"
        if audio_path != expected_path:
            # Move/copy file if needed
            shutil.copy(audio_path, expected_path)

    def mark_chunk_failed(self, fiction_id: str, book_number: int, chapter_number: int, chunk_index: int, error: str):
        """Mark a chunk as failed by writing error file."""
        chunks_dir = self.get_chunks_dir(fiction_id, book_number, chapter_number)
        err_file = chunks_dir / f"{chunk_index:03d}.error"
        with open(err_file, "w") as f:
            f.write(error)

    def get_pending_chunks(self, fiction_id: str, book_number: int, chapter_number: int) -> list[Chunk]:
        """Get all pending chunks for a chapter."""
        chunks = self.list_chunks(fiction_id, book_number, chapter_number)
        return [c for c in chunks if c.status == ChunkStatus.PENDING]

    def get_failed_chunks(self, fiction_id: str, book_number: int, chapter_number: int) -> list[Chunk]:
        """Get all failed chunks for a chapter."""
        chunks = self.list_chunks(fiction_id, book_number, chapter_number)
        return [c for c in chunks if c.status == ChunkStatus.FAILED]


# ============================================================================
# Convenience functions
# ============================================================================

def get_book_discovery() -> BookDiscovery:
    """Get a BookDiscovery instance."""
    return BookDiscovery()


def get_chapter_discovery() -> ChapterDiscovery:
    """Get a ChapterDiscovery instance."""
    return ChapterDiscovery()


def get_chunk_discovery() -> ChunkDiscovery:
    """Get a ChunkDiscovery instance."""
    return ChunkDiscovery()

