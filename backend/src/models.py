"""Pydantic models for the audiobook system.

All models are designed to be derived from the filesystem structure.
No database is used - state is determined by file existence.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class BookStatus(str, Enum):
    """Status of a book in the processing pipeline."""
    AVAILABLE = "available"  # Available on source (Royal Road) but not downloaded
    NOT_DOWNLOADED = "not_downloaded"  # Legacy: same as available
    DOWNLOADED = "downloaded"
    PROCESSING = "processing"
    READY = "ready"  # All audio complete
    EXPORTED = "exported"


class ChapterStatus(str, Enum):
    """Status of a chapter in the processing pipeline."""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADED = "downloaded"
    NORMALIZED = "normalized"
    CHUNKED = "chunked"
    PROCESSING = "processing"
    AUDIO_COMPLETE = "audio_complete"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    EXPORTED = "exported"


class ChunkStatus(str, Enum):
    """Status of a chunk in the processing pipeline."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Status of validation for a chunk."""
    NOT_VALIDATED = "not_validated"
    PASSED = "passed"
    FAILED = "failed"


# ============================================================================
# Book Models
# ============================================================================

class BookMetadata(BaseModel):
    """Metadata stored in book's metadata.json file."""
    fiction_id: str
    book_number: int
    title: str
    author: Optional[str] = None
    source_url: str
    scraped_at: datetime
    chapter_count: int = 0


class Book(BaseModel):
    """Book with computed status from filesystem."""
    fiction_id: str
    book_number: int
    title: str
    author: Optional[str] = None
    source_url: str
    scraped_at: datetime
    chapter_count: int = 0

    # Computed from filesystem
    path: Path
    chapters_downloaded: int = 0
    chapters_normalized: int = 0
    chapters_chunked: int = 0
    chapters_audio_complete: int = 0
    chapters_validated: int = 0
    chapters_exported: int = 0

    @computed_field
    @property
    def status(self) -> BookStatus:
        """Derive book status from chapter progress."""
        if self.chapters_exported == self.chapter_count and self.chapter_count > 0:
            return BookStatus.EXPORTED
        if self.chapters_audio_complete == self.chapter_count and self.chapter_count > 0:
            return BookStatus.READY
        if self.chapters_audio_complete > 0:
            return BookStatus.PROCESSING
        if self.chapters_downloaded > 0:
            return BookStatus.DOWNLOADED
        return BookStatus.NOT_DOWNLOADED

    @computed_field
    @property
    def progress_percent(self) -> float:
        """Calculate overall progress percentage."""
        if self.chapter_count == 0:
            return 0.0
        return (self.chapters_audio_complete / self.chapter_count) * 100

    class Config:
        arbitrary_types_allowed = True


class BookSummary(BaseModel):
    """Lightweight book info for dashboard."""
    fiction_id: str
    book_number: int
    title: str
    status: str
    progress_percent: float
    chapter_count: int
    chapters_complete: int  # Audio complete
    chapters_normalized: int = 0
    chapters_chunked: int = 0


# ============================================================================
# Chapter Models
# ============================================================================

class ChapterMetadata(BaseModel):
    """Metadata stored in chapter's metadata.json file."""
    chapter_number: int
    title: str
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    chunk_count: int = 0
    audio_duration_seconds: Optional[float] = None


class Chapter(BaseModel):
    """Chapter with computed status from filesystem."""
    chapter_number: int
    title: str
    source_url: Optional[str] = None
    scraped_at: Optional[datetime] = None
    chunk_count: int = 0
    audio_duration_seconds: Optional[float] = None

    # Computed from filesystem
    path: Path
    is_downloaded: bool = False
    is_normalized: bool = False
    is_chunked: bool = False
    chunks_completed: int = 0
    chunks_failed: int = 0
    is_audio_complete: bool = False
    is_validated: bool = False
    validation_passed: Optional[bool] = None
    is_exported: bool = False

    @computed_field
    @property
    def status(self) -> ChapterStatus:
        """Derive chapter status from file existence."""
        if self.is_exported:
            return ChapterStatus.EXPORTED
        if self.is_audio_complete:
            if self.is_validated:
                return ChapterStatus.VALIDATED if self.validation_passed else ChapterStatus.VALIDATION_FAILED
            return ChapterStatus.AUDIO_COMPLETE
        if self.chunks_completed > 0:
            return ChapterStatus.PROCESSING
        if self.is_chunked:
            return ChapterStatus.CHUNKED
        if self.is_normalized:
            return ChapterStatus.NORMALIZED
        if self.is_downloaded:
            return ChapterStatus.DOWNLOADED
        return ChapterStatus.NOT_DOWNLOADED

    @computed_field
    @property
    def progress_percent(self) -> float:
        """Calculate chunk completion percentage."""
        if self.chunk_count == 0:
            return 0.0
        return (self.chunks_completed / self.chunk_count) * 100

    class Config:
        arbitrary_types_allowed = True


class ChapterSummary(BaseModel):
    """Lightweight chapter info for lists."""
    chapter_number: int
    title: str
    status: str
    progress_percent: float
    chunk_count: int
    chunks_completed: int
    is_normalized: bool = False
    is_chunked: bool = False
    is_audio_complete: bool = False
    is_exported: bool = False


# ============================================================================
# Chunk Models
# ============================================================================

class Chunk(BaseModel):
    """Chunk with status derived from filesystem."""
    index: int  # 1-based index (001, 002, etc.)
    text: str
    text_start: int  # Character position in normalized text
    text_end: int

    # File paths
    text_path: Path
    audio_path: Optional[Path] = None

    # Status
    status: ChunkStatus = ChunkStatus.PENDING
    error: Optional[str] = None

    # Audio metadata (after generation)
    audio_duration_seconds: Optional[float] = None
    generation_time_seconds: Optional[float] = None

    # Validation
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    validation_similarity: Optional[float] = None
    validation_issues: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def has_audio(self) -> bool:
        """Check if audio file exists."""
        return self.audio_path is not None and self.audio_path.exists()

    class Config:
        arbitrary_types_allowed = True


class ChunkJob(BaseModel):
    """Job for processing a chunk."""
    fiction_id: str
    book_number: int
    chapter_number: int
    chunk_index: int
    text: str
    priority: int = 0  # Higher = processed first

    @computed_field
    @property
    def job_id(self) -> str:
        """Unique job identifier."""
        return f"{self.fiction_id}_{self.book_number}_{self.chapter_number}_{self.chunk_index}"


# ============================================================================
# Validation Models
# ============================================================================

class ChunkValidationResult(BaseModel):
    """Result of validating a single chunk."""
    chunk_index: int
    similarity: float
    passed: bool
    issues: list[str] = Field(default_factory=list)
    expected_text: Optional[str] = None
    transcribed_text: Optional[str] = None


class ChapterValidationResult(BaseModel):
    """Result of validating all chunks in a chapter."""
    chapter_number: int
    validated_at: datetime
    total_chunks: int
    passed_chunks: int
    failed_chunks: int
    chunks: dict[str, ChunkValidationResult] = Field(default_factory=dict)

    @computed_field
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_chunks == 0:
            return 0.0
        return (self.passed_chunks / self.total_chunks) * 100


# ============================================================================
# Queue Models
# ============================================================================

class CurrentJobInfo(BaseModel):
    """Info about the currently processing job."""
    fiction_id: str
    book_number: int
    chapter_number: int
    chunk_index: int
    chapter_title: Optional[str] = None


class QueuedChapterInfo(BaseModel):
    """Info about a chapter in the queue."""
    fiction_id: str
    fiction_name: Optional[str] = None
    book_number: int
    chapter_number: int
    chapter_title: Optional[str] = None
    pending_chunks: int
    total_chunks: int


class QueueStatus(BaseModel):
    """Current state of the processing queue."""
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    is_processing: bool = False
    current_job: Optional[str] = None
    current_job_info: Optional[CurrentJobInfo] = None
    queued_chapters: list[QueuedChapterInfo] = []

    @computed_field
    @property
    def total(self) -> int:
        """Total jobs in queue."""
        return self.pending + self.running + self.completed + self.failed


# ============================================================================
# API Response Models
# ============================================================================

class OperationResult(BaseModel):
    """Generic operation result."""
    success: bool
    message: str
    data: Optional[dict] = None


class ExportResult(BaseModel):
    """Result of exporting chapter audio."""
    chapter_number: int
    output_path: str
    success: bool
    error: Optional[str] = None

