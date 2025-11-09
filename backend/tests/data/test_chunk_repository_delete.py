"""Tests for ChunkRepository delete operations."""

import pytest
from src.data.db_repository import ChunkRepository
from src.data.database import db_session
from src.data.db_models import ChunkDB, BookDB, ChapterDB
from src.models.enums import ChunkStatus


def test_delete_by_chapter_removes_all_chunks():
    """Test that delete_by_chapter removes all chunks for a chapter."""
    
    # Create test chunks in database
    test_book_id = "test_book_delete"
    test_chapter = 99
    
    with db_session() as session:
        # First create book
        book = BookDB(
            id=test_book_id,
            title="Test Book for Deletion",
            author="Test Author",
        )
        session.add(book)
        
        # Then create chapter
        chapter = ChapterDB(
            id=f"{test_book_id}_{test_chapter}",
            book_id=test_book_id,
            chapter_number=test_chapter,
            number=test_chapter,
            title=f"Chapter {test_chapter}",
        )
        session.add(chapter)
        
        # Now create 5 test chunks
        for i in range(1, 6):
            chunk = ChunkDB(
                id=f"{test_book_id}_{test_chapter}_{i}",
                book_id=test_book_id,
                chapter_number=test_chapter,
                index=i,
                chapter_id=f"{test_book_id}_{test_chapter}",
                text_start=i * 100,
                text_end=(i + 1) * 100,
                status=ChunkStatus.PENDING.value,
            )
            session.add(chunk)
        session.commit()
    
    # Verify chunks were created
    chunks_before = ChunkRepository.get_by_chapter(test_book_id, test_chapter)
    assert len(chunks_before) == 5, "Should have created 5 test chunks"
    
    # Delete all chunks for the chapter
    deleted_count = ChunkRepository.delete_by_chapter(test_book_id, test_chapter)
    
    # Verify deletion
    assert deleted_count == 5, "Should have deleted all 5 chunks"
    
    chunks_after = ChunkRepository.get_by_chapter(test_book_id, test_chapter)
    assert len(chunks_after) == 0, "No chunks should remain after deletion"


def test_delete_by_chapter_only_affects_target_chapter():
    """Test that delete_by_chapter doesn't affect other chapters."""
    
    test_book_id = "test_book_delete_selective"
    
    with db_session() as session:
        # Create book first
        book = BookDB(
            id=test_book_id,
            title="Test Book for Selective Deletion",
            author="Test Author",
        )
        session.add(book)
        
        # Create chapter 1
        chapter1 = ChapterDB(
            id=f"{test_book_id}_1",
            book_id=test_book_id,
            chapter_number=1,
            number=1,
            title="Chapter 1",
        )
        session.add(chapter1)
        
        # Create chapter 2
        chapter2 = ChapterDB(
            id=f"{test_book_id}_2",
            book_id=test_book_id,
            chapter_number=2,
            number=2,
            title="Chapter 2",
        )
        session.add(chapter2)
        
        # Create chunks for chapter 1
        for i in range(1, 4):
            chunk = ChunkDB(
                id=f"{test_book_id}_1_{i}",
                book_id=test_book_id,
                chapter_number=1,
                index=i,
                chapter_id=f"{test_book_id}_1",
                text_start=i * 100,
                text_end=(i + 1) * 100,
                status=ChunkStatus.PENDING.value,
            )
            session.add(chunk)
        
        # Create chunks for chapter 2
        for i in range(1, 4):
            chunk = ChunkDB(
                id=f"{test_book_id}_2_{i}",
                book_id=test_book_id,
                chapter_number=2,
                index=i,
                chapter_id=f"{test_book_id}_2",
                text_start=i * 100,
                text_end=(i + 1) * 100,
                status=ChunkStatus.PENDING.value,
            )
            session.add(chunk)
        session.commit()
    
    # Delete only chapter 1
    deleted_count = ChunkRepository.delete_by_chapter(test_book_id, 1)
    assert deleted_count == 3, "Should have deleted 3 chunks from chapter 1"
    
    # Verify chapter 1 is gone but chapter 2 remains
    chapter1_chunks = ChunkRepository.get_by_chapter(test_book_id, 1)
    chapter2_chunks = ChunkRepository.get_by_chapter(test_book_id, 2)
    
    assert len(chapter1_chunks) == 0, "Chapter 1 chunks should be deleted"
    assert len(chapter2_chunks) == 3, "Chapter 2 chunks should remain"
    
    # Cleanup chapter 2
    ChunkRepository.delete_by_chapter(test_book_id, 2)


def test_delete_by_chapter_returns_zero_if_no_chunks():
    """Test that delete_by_chapter returns 0 if no chunks exist."""
    
    deleted_count = ChunkRepository.delete_by_chapter("nonexistent_book", 999)
    assert deleted_count == 0, "Should return 0 when no chunks exist"

