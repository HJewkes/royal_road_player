"""Shared utility functions for the audiobook system."""

from .filesystem import sanitize_filename, extract_series_name
from .retry import retry_with_backoff, retry_http, RetryError, is_transient_error
from .validation import (
    validate_fiction_id,
    validate_book_number,
    validate_chapter_number,
    FictionIdPath,
    BookNumberPath,
    ChapterNumberPath,
    BookNumberQuery,
)

__all__ = [
    # Filesystem utilities
    "sanitize_filename",
    "extract_series_name",
    # Retry utilities
    "retry_with_backoff",
    "retry_http",
    "RetryError",
    "is_transient_error",
    # Validation utilities
    "validate_fiction_id",
    "validate_book_number",
    "validate_chapter_number",
    # FastAPI annotated types
    "FictionIdPath",
    "BookNumberPath",
    "ChapterNumberPath",
    "BookNumberQuery",
]

