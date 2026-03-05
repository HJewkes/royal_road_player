"""API request and response models.

These Pydantic models define the shape of API requests and responses.
Separated from routes.py for clarity and to follow one-class-per-file principle.
"""

from typing import Optional

from pydantic import BaseModel

from src.models import BookStatus


# ============================================================================
# Fiction/Series Request Models
# ============================================================================


class AddFictionRequest(BaseModel):
    """Request to add a fiction by URL."""
    url: str


class FictionInfo(BaseModel):
    """Fiction info with name."""
    fiction_id: str
    name: str


class FictionPreview(BaseModel):
    """Preview of a fiction from Royal Road."""
    fiction_id: str
    title: str
    author: str | None
    url: str
    book_count: int
    books: list[dict] = []


class SeriesBookInfo(BaseModel):
    """Info about a book in a series (downloaded or not)."""
    book_number: int
    chapter_count: int
    is_downloaded: bool
    # If downloaded, include summary info
    chapters_normalized: int = 0
    chapters_chunked: int = 0
    chapters_complete: int = 0  # Audio complete
    chapters_exported: int = 0
    progress_percent: float = 0.0
    status: BookStatus = BookStatus.NOT_DOWNLOADED
    # Royal Road chapter count (when refreshed); enables "new chapters" detection
    chapters_on_royal_road: Optional[int] = None


# ============================================================================
# Download Request Models
# ============================================================================


class DownloadRequest(BaseModel):
    """Request to download a book."""
    fiction_id: str
    book_number: int


# ============================================================================
# Processing Request Models
# ============================================================================


class NormalizeRequest(BaseModel):
    """Request to normalize chapters."""
    fiction_id: str
    book_number: int
    chapter_numbers: Optional[list[int]] = None


class ChunkRequest(BaseModel):
    """Request to chunk chapters."""
    fiction_id: str
    book_number: int
    chapter_numbers: Optional[list[int]] = None


class GenerateRequest(BaseModel):
    """Request to generate audio."""
    fiction_id: str
    book_number: int
    chapter_numbers: Optional[list[int]] = None


# ============================================================================
# Validation Request Models
# ============================================================================


class ValidateRequest(BaseModel):
    """Request to validate audio."""
    fiction_id: str
    book_number: int
    chapter_number: int


# ============================================================================
# Export Request Models
# ============================================================================


class ExportRequest(BaseModel):
    """Request to export audio."""
    fiction_id: str
    book_number: int
    chapter_number: int
    format: str = "mp3"  # Default to audiobook-optimized MP3


# ============================================================================
# Backfill Request/Response Models
# ============================================================================


class BackfillTitlesRequest(BaseModel):
    """Request to backfill chapter titles from Royal Road."""
    fiction_id: str
    book_number: int


class BackfillResult(BaseModel):
    """Result of backfill operation."""
    success: bool
    message: str
    updated: int
    skipped: int
    errors: list[str]

