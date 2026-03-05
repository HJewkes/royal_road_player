"""Filesystem-related utility functions.

Provides safe filename generation and path utilities used across
the scraper, exporter, and discovery modules.
"""

import re


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Make a string safe for filesystem use on all major platforms.

    Removes characters that are invalid on Windows, macOS, or Linux filesystems.
    Normalizes whitespace and truncates to max_length if needed.

    Args:
        name: Raw filename string (may contain invalid characters)
        max_length: Maximum length of resulting filename (default 100)

    Returns:
        Sanitized filename safe for all major filesystems.
        Returns "untitled" if the result would be empty.

    Examples:
        >>> sanitize_filename('My Book: Chapter 1')
        'My Book Chapter 1'
        >>> sanitize_filename('A' * 150, max_length=50)
        'AAAAA...'  # truncated to 50 chars
    """
    # Remove characters invalid on Windows/macOS/Linux: < > : " / \ | ? *
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)

    # Normalize whitespace (collapse multiple spaces, strip leading/trailing)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Truncate if exceeds max length, avoiding partial words/trailing punctuation
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip(' .-_')

    return sanitized or "untitled"


def extract_series_name(title: str) -> str:
    """
    Extract series name from a book title by removing "- Book N" suffix.

    Handles various separators (hyphen, en-dash) and case-insensitive matching.

    Args:
        title: Full book title, e.g., "Player Manager - Book 7"

    Returns:
        Series name without the book number suffix.
        Returns the original title stripped if no suffix found.

    Examples:
        >>> extract_series_name('Player Manager - Book 7')
        'Player Manager'
        >>> extract_series_name('My Series – Book 12')  # en-dash
        'My Series'
        >>> extract_series_name('Standalone Novel')
        'Standalone Novel'
    """
    # Remove "- Book N" or "– Book N" suffix (case insensitive)
    name = re.sub(r'\s*[-–]\s*Book\s+\d+\s*$', '', title, flags=re.IGNORECASE)
    return name.strip()


