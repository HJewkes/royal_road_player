"""Utilities for sanitizing filenames."""

import re
from pathlib import Path


def sanitize_filename(name: str, max_length: int = 100, preserve_spaces: bool = True) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        name: String to sanitize
        max_length: Maximum length of the filename
        preserve_spaces: If True, keep spaces; if False, convert to hyphens

    Returns:
        Sanitized filename-safe string
    """
    # Remove or replace invalid characters
    # Keep alphanumeric, spaces, hyphens, underscores, and periods
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    
    if preserve_spaces:
        # Normalize whitespace (multiple spaces to single space)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        # Remove leading/trailing spaces
        sanitized = sanitized.strip()
    else:
        # Replace multiple spaces/underscores/hyphens with single hyphen
        sanitized = re.sub(r'[\s_\-]+', '-', sanitized)
        # Remove leading/trailing dashes and dots
        sanitized = sanitized.strip('.-_')
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('.-_ ')
    
    return sanitized if sanitized else "untitled"


def sanitize_chapter_filename(chapter_number: int, chapter_title: str, max_length: int = 150) -> str:
    """
    Create a sanitized filename for a chapter.

    Args:
        chapter_number: Chapter number (for ordering)
        chapter_title: Chapter title
        max_length: Maximum filename length

    Returns:
        Sanitized filename like "07-01 - The First Cut is the Deepest.txt"
    """
    # Extract chapter number from title if it's in format "7.1" or "7.1 - Title"
    chapter_match = re.match(r'^(\d+)\.(\d+)\s*-\s*(.+)$', chapter_title)
    if chapter_match:
        book_num = chapter_match.group(1)
        chap_num = chapter_match.group(2)
        title = chapter_match.group(3)
        # Format: "07-01 - Title.txt"
        prefix = f"{int(book_num):02d}-{int(chap_num):02d}"
    else:
        # Fallback: use chapter_number
        prefix = f"{chapter_number:04d}"
        title = chapter_title
    
    # Sanitize title
    sanitized_title = sanitize_filename(title, max_length=max_length - len(prefix) - 4)  # -4 for " - .txt"
    
    # Combine
    filename = f"{prefix} - {sanitized_title}.txt"
    
    # Final length check
    if len(filename) > max_length:
        # Truncate title part
        title_max = max_length - len(prefix) - 7  # " - .txt"
        sanitized_title = sanitize_filename(title, max_length=title_max)
        filename = f"{prefix} - {sanitized_title}.txt"
    
    return filename

