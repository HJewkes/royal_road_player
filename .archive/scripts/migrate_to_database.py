#!/usr/bin/env python3
"""Migration script to populate database from existing metadata.json files."""

import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from src.data.database import init_db, get_session
from src.data.db_repository import BookRepository, ChapterRepository, ChunkRepository
from src.data.data_synchronizer import DataSynchronizer
from src.models.enums import ChunkStatus
from src.utils.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_books(session, synchronizer: DataSynchronizer):
    """Migrate all books from filesystem to database."""
    logger.info("Migrating books...")
    books = synchronizer.load_books()
    
    for book in books:
        try:
            BookRepository.create_or_update(book, session)
            logger.debug(f"Migrated book: {book.id}")
        except Exception as e:
            logger.error(f"Failed to migrate book {book.id}: {e}")
    
    session.commit()
    logger.info(f"Migrated {len(books)} books")


def migrate_chapters(session, synchronizer: DataSynchronizer):
    """Migrate all chapters from filesystem to database."""
    logger.info("Migrating chapters...")
    books = synchronizer.load_books()
    total_chapters = 0
    
    for book in books:
        try:
            chapters = synchronizer.load_chapters(book.id)
            for chapter in chapters:
                try:
                    ChapterRepository.create_or_update(chapter, session)
                    total_chapters += 1
                except Exception as e:
                    logger.error(f"Failed to migrate chapter {chapter.id}: {e}")
        except Exception as e:
            logger.error(f"Failed to load chapters for book {book.id}: {e}")
    
    session.commit()
    logger.info(f"Migrated {total_chapters} chapters")


def migrate_chunks(session, synchronizer: DataSynchronizer):
    """Migrate all chunks from filesystem to database."""
    logger.info("Migrating chunks...")
    books = synchronizer.load_books()
    total_chunks = 0
    
    for book in books:
        try:
            chapters = synchronizer.load_chapters(book.id)
            for chapter in chapters:
                if chapter.chapter_number is None:
                    continue
                
                try:
                    chunks = synchronizer.load_chunks(book.id, chapter.chapter_number)
                    for chunk in chunks:
                        try:
                            # Ensure chapter_id is set
                            if not chunk.chapter_id and chapter.id:
                                chunk = chunk.__class__(
                                    **{**chunk.__dict__, 'chapter_id': chapter.id}
                                )
                            ChunkRepository.create_or_update(chunk, chapter.chapter_number, session)
                            total_chunks += 1
                            
                            if total_chunks % 100 == 0:
                                session.commit()
                                logger.info(f"Migrated {total_chunks} chunks...")
                        except Exception as e:
                            logger.error(f"Failed to migrate chunk {chunk.index} for chapter {chapter.chapter_number}: {e}")
                except Exception as e:
                    logger.error(f"Failed to load chunks for chapter {chapter.chapter_number}: {e}")
        except Exception as e:
            logger.error(f"Failed to process book {book.id}: {e}")
    
    session.commit()
    logger.info(f"Migrated {total_chunks} chunks total")


def verify_migration(session):
    """Verify migration by comparing counts."""
    logger.info("Verifying migration...")
    
    from src.data.db_models import BookDB, ChapterDB, ChunkDB
    from sqlalchemy import func
    
    book_count = session.query(func.count(BookDB.id)).scalar()
    chapter_count = session.query(func.count(ChapterDB.id)).scalar()
    chunk_count = session.query(func.count(ChunkDB.id)).scalar()
    completed_chunks = session.query(func.count(ChunkDB.id)).filter(ChunkDB.status == ChunkStatus.COMPLETED.value).scalar()
    
    logger.info(f"Database contains:")
    logger.info(f"  Books: {book_count}")
    logger.info(f"  Chapters: {chapter_count}")
    logger.info(f"  Chunks: {chunk_count}")
    logger.info(f"  Completed chunks: {completed_chunks}")


def main():
    """Run migration."""
    logger.info("Starting database migration...")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Create session
    session = get_session()
    
    try:
        # Load synchronizer for reading filesystem
        settings = get_settings()
        synchronizer = DataSynchronizer(books_dir=settings.books_dir)
        
        # Migrate data
        migrate_books(session, synchronizer)
        migrate_chapters(session, synchronizer)
        migrate_chunks(session, synchronizer)
        
        # Verify
        verify_migration(session)
        
        logger.info("✅ Migration completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

