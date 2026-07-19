"""Tests for the discovery module."""

import json
import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from src.discovery import BookDiscovery, ChapterDiscovery, ChunkDiscovery
from src.models import BookMetadata, ChapterMetadata


@pytest.fixture
def temp_books_dir():
    """Create a temporary books directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestBookDiscovery:
    """Tests for BookDiscovery."""

    def test_list_empty_fictions(self, temp_books_dir):
        """Test listing fictions from empty directory."""
        discovery = BookDiscovery(books_dir=temp_books_dir)
        assert discovery.list_fictions() == []

    def test_create_and_get_book(self, temp_books_dir):
        """Test creating and retrieving a book."""
        discovery = BookDiscovery(books_dir=temp_books_dir)

        metadata = BookMetadata(
            fiction_id="12345",
            book_number=1,
            title="Test Book",
            author="Test Author",
            source_url="https://example.com",
            scraped_at=datetime.utcnow(),
            chapter_count=5,
        )

        book = discovery.create_book(metadata)
        assert book.fiction_id == "12345"
        assert book.book_number == 1
        assert book.title == "Test Book"

        # Retrieve the book
        retrieved = discovery.get_book("12345", 1)
        assert retrieved is not None
        assert retrieved.fiction_id == "12345"
        assert retrieved.title == "Test Book"

    def test_list_books(self, temp_books_dir):
        """Test listing all books for a fiction."""
        discovery = BookDiscovery(books_dir=temp_books_dir)

        # Create two books
        for i in [1, 2]:
            metadata = BookMetadata(
                fiction_id="12345",
                book_number=i,
                title=f"Test Book {i}",
                author="Test Author",
                source_url="https://example.com",
                scraped_at=datetime.utcnow(),
            )
            discovery.create_book(metadata)

        books = discovery.list_books("12345")
        assert len(books) == 2
        assert books[0].book_number == 1
        assert books[1].book_number == 2


class TestChapterDiscovery:
    """Tests for ChapterDiscovery."""

    def test_create_and_get_chapter(self, temp_books_dir):
        """Test creating and retrieving a chapter."""
        # First create a book
        book_discovery = BookDiscovery(books_dir=temp_books_dir)
        book_meta = BookMetadata(
            fiction_id="12345",
            book_number=1,
            title="Test Book",
            author=None,
            source_url="https://example.com",
            scraped_at=datetime.utcnow(),
        )
        book_discovery.create_book(book_meta)

        # Now create a chapter
        chapter_discovery = ChapterDiscovery(books_dir=temp_books_dir)
        chapter_meta = ChapterMetadata(
            chapter_number=1,
            title="Chapter 1",
            source_url="https://example.com/chapter/1",
            scraped_at=datetime.utcnow(),
        )
        chapter = chapter_discovery.create_chapter("12345", 1, chapter_meta)

        assert chapter.chapter_number == 1
        assert chapter.title == "Chapter 1"

        # Retrieve the chapter
        retrieved = chapter_discovery.get_chapter("12345", 1, 1)
        assert retrieved is not None
        assert retrieved.chapter_number == 1

    def test_save_and_get_text(self, temp_books_dir):
        """Test saving and retrieving raw/normalized text."""
        book_discovery = BookDiscovery(books_dir=temp_books_dir)
        book_meta = BookMetadata(
            fiction_id="12345",
            book_number=1,
            title="Test Book",
            author=None,
            source_url="https://example.com",
            scraped_at=datetime.utcnow(),
        )
        book_discovery.create_book(book_meta)

        chapter_discovery = ChapterDiscovery(books_dir=temp_books_dir)
        chapter_meta = ChapterMetadata(
            chapter_number=1,
            title="Chapter 1",
        )
        chapter_discovery.create_chapter("12345", 1, chapter_meta)

        # Save raw text
        raw_text = "This is the raw chapter text."
        chapter_discovery.save_raw_text("12345", 1, 1, raw_text)

        # Retrieve raw text
        retrieved_raw = chapter_discovery.get_raw_text("12345", 1, 1)
        assert retrieved_raw == raw_text

        # Save normalized text
        normalized = "This is the normalized chapter text."
        chapter_discovery.save_normalized_text("12345", 1, 1, normalized)

        # Retrieve normalized text
        retrieved_norm = chapter_discovery.get_normalized_text("12345", 1, 1)
        assert retrieved_norm == normalized


class TestChapterCompletionMarker:
    """Tests for the durable completion marker that survives pruning."""

    def _make_chapter(self, temp_books_dir):
        BookDiscovery(books_dir=temp_books_dir).create_book(
            BookMetadata(
                fiction_id="12345",
                book_number=1,
                title="Test Book",
                author=None,
                source_url="https://example.com",
                scraped_at=datetime.utcnow(),
            )
        )
        chapter_discovery = ChapterDiscovery(books_dir=temp_books_dir)
        chapter_discovery.create_chapter(
            "12345",
            1,
            ChapterMetadata(
                chapter_number=1,
                title="Real Title",
                source_url="https://example.com/chapter/1",
                scraped_at=datetime.utcnow(),
            ),
        )
        return chapter_discovery

    def test_mark_sets_marker_and_preserves_existing_fields(self, temp_books_dir):
        chapter_discovery = self._make_chapter(temp_books_dir)

        chapter_discovery.mark_chapter_completed("12345", 1, 1, Path("/exports/ch1.mp3"))

        metadata_path = chapter_discovery.get_chapter_path("12345", 1, 1) / "metadata.json"
        data = json.loads(metadata_path.read_text())
        assert data["completed_at"] is not None
        assert data["export_path"] == "/exports/ch1.mp3"
        # Read-merge-write must not clobber the fields written at scrape time.
        assert data["title"] == "Real Title"
        assert data["source_url"] == "https://example.com/chapter/1"

    def test_is_chapter_completed_reflects_marker(self, temp_books_dir):
        chapter_discovery = self._make_chapter(temp_books_dir)

        assert chapter_discovery.is_chapter_completed("12345", 1, 1) is False
        chapter_discovery.mark_chapter_completed("12345", 1, 1, Path("/exports/ch1.mp3"))
        assert chapter_discovery.is_chapter_completed("12345", 1, 1) is True

    def test_marker_makes_chapter_exported_without_files_on_disk(self, temp_books_dir):
        """A completed-then-pruned chapter (no audio.wav, no export file) must
        still read as exported so recovery/audits don't treat it as unfinished."""
        chapter_discovery = self._make_chapter(temp_books_dir)

        before = chapter_discovery.get_chapter("12345", 1, 1)
        assert before.is_exported is False

        chapter_discovery.mark_chapter_completed("12345", 1, 1, Path("/exports/ch1.mp3"))

        after = chapter_discovery.get_chapter("12345", 1, 1)
        assert after.is_exported is True
        assert after.completed_at is not None
        assert after.export_path == "/exports/ch1.mp3"


class TestChunkDiscovery:
    """Tests for ChunkDiscovery."""

    def test_save_and_list_chunks(self, temp_books_dir):
        """Test saving and listing chunks."""
        # Setup book and chapter
        book_discovery = BookDiscovery(books_dir=temp_books_dir)
        book_meta = BookMetadata(
            fiction_id="12345",
            book_number=1,
            title="Test Book",
            author=None,
            source_url="https://example.com",
            scraped_at=datetime.utcnow(),
        )
        book_discovery.create_book(book_meta)

        chapter_discovery = ChapterDiscovery(books_dir=temp_books_dir)
        chapter_meta = ChapterMetadata(chapter_number=1, title="Chapter 1")
        chapter_discovery.create_chapter("12345", 1, chapter_meta)

        # Save chunks
        chunk_discovery = ChunkDiscovery(books_dir=temp_books_dir)
        chunks_data = [
            (1, "First chunk text."),
            (2, "Second chunk text."),
            (3, "Third chunk text."),
        ]
        chunk_discovery.save_chunks("12345", 1, 1, chunks_data)

        # List chunks
        chunks = chunk_discovery.list_chunks("12345", 1, 1)
        assert len(chunks) == 3
        assert chunks[0].index == 1
        assert chunks[0].text == "First chunk text."

    def test_get_pending_chunks(self, temp_books_dir):
        """Test getting pending chunks (no audio)."""
        # Setup
        book_discovery = BookDiscovery(books_dir=temp_books_dir)
        book_meta = BookMetadata(
            fiction_id="12345",
            book_number=1,
            title="Test Book",
            author=None,
            source_url="https://example.com",
            scraped_at=datetime.utcnow(),
        )
        book_discovery.create_book(book_meta)

        chapter_discovery = ChapterDiscovery(books_dir=temp_books_dir)
        chapter_meta = ChapterMetadata(chapter_number=1, title="Chapter 1")
        chapter_discovery.create_chapter("12345", 1, chapter_meta)

        chunk_discovery = ChunkDiscovery(books_dir=temp_books_dir)
        chunks_data = [(1, "Text 1"), (2, "Text 2")]
        chunk_discovery.save_chunks("12345", 1, 1, chunks_data)

        # All should be pending (no audio files)
        pending = chunk_discovery.get_pending_chunks("12345", 1, 1)
        assert len(pending) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


