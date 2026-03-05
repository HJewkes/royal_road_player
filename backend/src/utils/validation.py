"""Input validation utilities for API parameters.

Provides validators and sanitizers for user-provided path parameters
to prevent directory traversal and other security issues.
"""

import re
from typing import Annotated

from fastapi import HTTPException, Path, Query


# ============================================================================
# Validation Functions
# ============================================================================


def validate_fiction_id(fiction_id: str) -> str:
    """
    Validate and sanitize a fiction ID.

    Fiction IDs should be numeric strings (from Royal Road).
    
    Args:
        fiction_id: The fiction ID to validate
        
    Returns:
        Validated fiction ID
        
    Raises:
        HTTPException: If the fiction ID is invalid
    """
    if not fiction_id:
        raise HTTPException(status_code=400, detail="Fiction ID is required")
    
    # Fiction IDs from Royal Road are always numeric
    if not re.match(r'^\d+$', fiction_id):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid fiction ID: '{fiction_id}'. Must be a numeric string."
        )
    
    # Prevent excessively long IDs
    if len(fiction_id) > 20:
        raise HTTPException(
            status_code=400,
            detail="Fiction ID is too long"
        )
    
    return fiction_id


def validate_book_number(book_number: int) -> int:
    """
    Validate a book number.
    
    Book numbers must be positive integers.
    
    Args:
        book_number: The book number to validate
        
    Returns:
        Validated book number
        
    Raises:
        HTTPException: If the book number is invalid
    """
    if book_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid book number: {book_number}. Must be a positive integer."
        )
    
    if book_number > 9999:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid book number: {book_number}. Value is unreasonably large."
        )
    
    return book_number


def validate_chapter_number(chapter_number: int) -> int:
    """
    Validate a chapter number.
    
    Chapter numbers must be positive integers.
    
    Args:
        chapter_number: The chapter number to validate
        
    Returns:
        Validated chapter number
        
    Raises:
        HTTPException: If the chapter number is invalid
    """
    if chapter_number < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chapter number: {chapter_number}. Must be a positive integer."
        )
    
    if chapter_number > 99999:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chapter number: {chapter_number}. Value is unreasonably large."
        )
    
    return chapter_number


# ============================================================================
# FastAPI Annotated Types
# ============================================================================

# Annotated path parameters with built-in validation
FictionIdPath = Annotated[
    str,
    Path(
        description="Royal Road fiction ID (numeric)",
        pattern=r'^\d+$',
        min_length=1,
        max_length=20,
        examples=["58187", "124774"]
    )
]

BookNumberPath = Annotated[
    int,
    Path(
        description="Book number within the fiction",
        ge=1,
        le=9999,
        examples=[1, 7, 12]
    )
]

ChapterNumberPath = Annotated[
    int,
    Path(
        description="Chapter number within the book",
        ge=1,
        le=99999,
        examples=[1, 25, 100]
    )
]

# Optional book number for query parameters
BookNumberQuery = Annotated[
    int | None,
    Query(
        description="Optional book number to filter by",
        ge=1,
        le=9999
    )
]


