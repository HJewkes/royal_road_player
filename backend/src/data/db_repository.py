"""Database repository for CRUD operations."""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, desc
from sqlalchemy.sql import text

from src.data.database import get_session, db_session
from src.data.db_models import BookDB, ChapterDB, ChunkDB
from src.models.book import Book
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus

logger = logging.getLogger(__name__)


class BookRepository:
    """Repository for book operations."""
    
    @staticmethod
    def get_all(session: Optional[Session] = None) -> List[Book]:
        """Get all books."""
        if session is None:
            with db_session() as session:
                return BookRepository.get_all(session)
        
        books = session.query(BookDB).all()
        return [BookRepository._to_model(book) for book in books]
    
    @staticmethod
    def get_by_id(book_id: str, session: Optional[Session] = None) -> Optional[Book]:
        """Get book by ID."""
        if session is None:
            with db_session() as session:
                return BookRepository.get_by_id(book_id, session)
        
        book_db = session.query(BookDB).filter(BookDB.id == book_id).first()
        return BookRepository._to_model(book_db) if book_db else None
    
    @staticmethod
    def get_by_path(path: str, session: Optional[Session] = None) -> Optional[Book]:
        """Get book by path."""
        if session is None:
            with db_session() as session:
                return BookRepository.get_by_path(path, session)
        
        book_db = session.query(BookDB).filter(BookDB.path == path).first()
        return BookRepository._to_model(book_db) if book_db else None
    
    @staticmethod
    def create_or_update(book: Book, session: Optional[Session] = None) -> BookDB:
        """Create or update a book."""
        if session is None:
            with db_session() as session:
                return BookRepository.create_or_update(book, session)
        
        book_db = session.query(BookDB).filter(BookDB.id == book.id).first()
        if book_db:
            # Update existing
            book_db.title = book.title
            book_db.author = book.author
            book_db.url = book.url
            book_db.filter_book_number = book.filter_book_number
            book_db.path = book.path
        else:
            # Create new
            book_db = BookDB(
                id=book.id,
                title=book.title,
                author=book.author,
                url=book.url,
                filter_book_number=book.filter_book_number,
                path=book.path,
            )
            session.add(book_db)
        
        return book_db
    
    @staticmethod
    def _to_model(book_db: BookDB) -> Book:
        """Convert database model to domain model."""
        return Book(
            id=book_db.id,
            title=book_db.title,
            author=book_db.author,
            url=book_db.url,
            filter_book_number=book_db.filter_book_number,
            path=book_db.path,
        )


class ChapterRepository:
    """Repository for chapter operations."""
    
    @staticmethod
    def get_by_book(book_id: str, session: Optional[Session] = None) -> List[Chapter]:
        """Get all chapters for a book."""
        if session is None:
            with db_session() as session:
                return ChapterRepository.get_by_book(book_id, session)
        
        chapters = session.query(ChapterDB).filter(ChapterDB.book_id == book_id).order_by(ChapterDB.chapter_number).all()
        return [ChapterRepository._to_model(ch) for ch in chapters]
    
    @staticmethod
    def get_by_id(chapter_id: str, session: Optional[Session] = None) -> Optional[Chapter]:
        """Get chapter by ID."""
        if session is None:
            with db_session() as session:
                return ChapterRepository.get_by_id(chapter_id, session)
        
        chapter_db = session.query(ChapterDB).filter(ChapterDB.id == chapter_id).first()
        return ChapterRepository._to_model(chapter_db) if chapter_db else None
    
    @staticmethod
    def get_by_book_and_number(book_id: str, chapter_number: int, session: Optional[Session] = None) -> Optional[Chapter]:
        """Get chapter by book ID and chapter number."""
        if session is None:
            with db_session() as session:
                return ChapterRepository.get_by_book_and_number(book_id, chapter_number, session)
        
        chapter_db = session.query(ChapterDB).filter(
            and_(ChapterDB.book_id == book_id, ChapterDB.chapter_number == chapter_number)
        ).first()
        return ChapterRepository._to_model(chapter_db) if chapter_db else None
    
    @staticmethod
    def create_or_update(chapter: Chapter, session: Optional[Session] = None) -> ChapterDB:
        """Create or update a chapter."""
        if session is None:
            with db_session() as session:
                return ChapterRepository.create_or_update(chapter, session)
        
        chapter_id = chapter.id or f"{chapter.book_id}_{chapter.chapter_number:02d}"
        chapter_db = session.query(ChapterDB).filter(ChapterDB.id == chapter_id).first()
        if chapter_db:
            # Update existing
            chapter_db.title = chapter.title
            chapter_db.number = chapter.number
            chapter_db.url = chapter.url
            chapter_db.path = chapter.path
        else:
            # Create new
            chapter_db = ChapterDB(
                id=chapter_id,
                book_id=chapter.book_id,
                chapter_number=chapter.chapter_number or 0,
                title=chapter.title,
                number=chapter.number,
                url=chapter.url,
                path=chapter.path,
            )
            session.add(chapter_db)
        
        return chapter_db
    
    @staticmethod
    def _to_model(chapter_db: ChapterDB) -> Chapter:
        """Convert database model to domain model."""
        return Chapter(
            book_id=chapter_db.book_id,
            title=chapter_db.title,
            id=chapter_db.id,
            chapter_number=chapter_db.chapter_number,
            number=chapter_db.number,
            url=chapter_db.url,
            path=chapter_db.path,
        )


class ChunkRepository:
    """Repository for chunk operations."""
    
    @staticmethod
    def get_by_chapter(book_id: str, chapter_number: int, session: Optional[Session] = None) -> List[Chunk]:
        """Get all chunks for a chapter."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_by_chapter(book_id, chapter_number, session)
        
        chunks = session.query(ChunkDB).filter(
            and_(ChunkDB.book_id == book_id, ChunkDB.chapter_number == chapter_number)
        ).order_by(ChunkDB.index).all()
        return [ChunkRepository._to_model(ch) for ch in chunks]
    
    @staticmethod
    def get_by_id(chunk_id: str, session: Optional[Session] = None) -> Optional[Chunk]:
        """Get chunk by ID."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_by_id(chunk_id, session)
        
        chunk_db = session.query(ChunkDB).filter(ChunkDB.id == chunk_id).first()
        return ChunkRepository._to_model(chunk_db) if chunk_db else None
    
    @staticmethod
    def get_by_book_chapter_index(book_id: str, chapter_number: int, chunk_index: int, session: Optional[Session] = None) -> Optional[Chunk]:
        """Get chunk by book, chapter, and index."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_by_book_chapter_index(book_id, chapter_number, chunk_index, session)
        
        chunk_db = session.query(ChunkDB).filter(
            and_(
                ChunkDB.book_id == book_id,
                ChunkDB.chapter_number == chapter_number,
                ChunkDB.index == chunk_index
            )
        ).first()
        return ChunkRepository._to_model(chunk_db) if chunk_db else None
    
    @staticmethod
    def count_by_status(book_id: Optional[str] = None, chapter_number: Optional[int] = None, status: ChunkStatus = ChunkStatus.COMPLETED, session: Optional[Session] = None) -> int:
        """Count chunks by status (fast aggregation query)."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.count_by_status(book_id, chapter_number, status, session)
        
        query = session.query(func.count(ChunkDB.id)).filter(ChunkDB.status == status.value)
        
        if book_id:
            query = query.filter(ChunkDB.book_id == book_id)
        if chapter_number is not None:
            query = query.filter(ChunkDB.chapter_number == chapter_number)
        
        return query.scalar() or 0
    
    @staticmethod
    def get_pending_chunks_ordered(limit: int = 10, session: Optional[Session] = None, include_failed: bool = True) -> List[tuple]:
        """
        Get pending chunks (and optionally failed chunks) ordered by book_id, chapter_number, chunk_index (earliest first).
        Efficient SQL query for job queue processing.
        
        Args:
            limit: Maximum number of chunks to return
            session: Optional database session
            include_failed: If True, also include failed chunks for automatic retry
            
        Returns:
            List of (Chunk, chapter_number) tuples ordered by book/chapter/index
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_pending_chunks_ordered(limit, session, include_failed)
        
        if include_failed:
            # Get both pending and failed chunks
            chunks_db = session.query(ChunkDB).filter(
                ChunkDB.status.in_([ChunkStatus.PENDING.value, ChunkStatus.FAILED.value])
            ).order_by(
                ChunkDB.book_id,
                ChunkDB.chapter_number,
                ChunkDB.index
            ).limit(limit).all()
        else:
            # Only pending chunks
            chunks_db = session.query(ChunkDB).filter(
                ChunkDB.status == ChunkStatus.PENDING.value
            ).order_by(
                ChunkDB.book_id,
                ChunkDB.chapter_number,
                ChunkDB.index
            ).limit(limit).all()
        
        return [(ChunkRepository._to_model(ch), ch.chapter_number) for ch in chunks_db]
    
    @staticmethod
    def calculate_eta(
        pending_jobs: List[tuple],  # List of (book_id, chapter_number, chunk_index) tuples
        session: Optional[Session] = None
    ) -> dict:
        """
        Calculate ETA for pending jobs using SQL queries with trimmed mean.
        
        Uses trimmed mean approach: Get average time per chunk from recent completed chunks,
        excluding top and bottom 10% outliers for more accurate estimates.
        Multiplies average by number of pending jobs to estimate remaining time.
        
        Args:
            pending_jobs: List of (book_id, chapter_number, chunk_index) tuples for pending jobs
            session: Optional database session
            
        Returns:
            Dictionary with 'estimated_seconds_remaining', 'avg_time_per_chunk', 'avg_time_per_char'
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.calculate_eta(pending_jobs, session)
        
        # Default fallbacks
        avg_time_per_chunk = 7.0
        avg_time_per_char = 0.03
        
        if not pending_jobs:
            return {
                'estimated_seconds_remaining': 0,
                'avg_time_per_chunk': avg_time_per_chunk,
                'avg_time_per_char': avg_time_per_char,
            }
        
        # Get recent completed chunks (last 50) for trimmed mean calculation
        # We'll trim top and bottom 10% to remove outliers using SQL window functions
        # Use raw SQL for trimmed mean calculation (more reliable with SQLite window functions)
        trimmed_mean_query = text("""
            WITH ranked_chunks AS (
                SELECT 
                    generation_time_seconds,
                    (text_end - text_start) as text_length,
                    CAST(generation_time_seconds AS REAL) / CAST((text_end - text_start) AS REAL) as time_per_char,
                    ROW_NUMBER() OVER (ORDER BY CAST(generation_time_seconds AS REAL) / CAST((text_end - text_start) AS REAL)) as rank_asc,
                    COUNT() OVER () as total_count
                FROM chunks
                WHERE status = :status
                    AND generation_time_seconds IS NOT NULL
                    AND generation_time_seconds > 0
                    AND text_end IS NOT NULL
                    AND text_start IS NOT NULL
                    AND (text_end - text_start) > 0
                ORDER BY updated_at DESC
                LIMIT 50
            ),
            trimmed_chunks AS (
                SELECT 
                    generation_time_seconds,
                    text_length,
                    time_per_char
                FROM ranked_chunks
                WHERE total_count <= 5 OR (
                    -- Keep middle 80%: exclude bottom 10% (low ranks) and top 10% (high ranks)
                    -- rank_asc is ordered ascending by time_per_char (1 = fastest, highest = slowest)
                    -- Use ROUND to ensure we get at least some data even with small samples
                    rank_asc > ROUND(total_count * 0.1)
                    AND rank_asc <= ROUND(total_count * 0.9)
                )
            )
            SELECT 
                AVG(time_per_char) as avg_time_per_char,
                AVG(generation_time_seconds) as avg_time_per_chunk,
                AVG(text_length) as avg_text_length,
                COUNT(*) as trimmed_count
            FROM trimmed_chunks
        """)
        
        result = session.execute(
            trimmed_mean_query,
            {"status": ChunkStatus.COMPLETED.value}
        ).first()
        
        # Check if we got valid trimmed results with enough data points
        trimmed_count = result.trimmed_count if result else 0
        use_trimmed = result and result.avg_time_per_char and result.avg_time_per_char > 0 and trimmed_count >= 5
        
        # Store result object for avg_text_length access later
        final_result = None
        untrimmed_result = None
        
        if use_trimmed:
            avg_time_per_char = float(result.avg_time_per_char)
            if result.avg_time_per_chunk:
                avg_time_per_chunk = float(result.avg_time_per_chunk)
            final_result = result  # Use trimmed result for avg_text_length
            logger.debug(f"Using trimmed mean: {trimmed_count} chunks, avg_time_per_char={avg_time_per_char:.4f}")
        else:
            # Fallback to untrimmed mean if trimmed mean has insufficient data
            logger.debug(f"Falling back to untrimmed mean (trimmed_count={trimmed_count})")
            # Get last 50 chunks first, then aggregate
            recent_chunk_ids = session.query(ChunkDB.id).filter(
                ChunkDB.status == ChunkStatus.COMPLETED.value,
                ChunkDB.generation_time_seconds.isnot(None),
                ChunkDB.generation_time_seconds > 0,
                ChunkDB.text_end.isnot(None),
                ChunkDB.text_start.isnot(None),
                (ChunkDB.text_end - ChunkDB.text_start) > 0
            ).order_by(desc(ChunkDB.updated_at)).limit(50).subquery()
            
            untrimmed_result = session.query(
                func.avg(ChunkDB.generation_time_seconds / (ChunkDB.text_end - ChunkDB.text_start)).label('avg_time_per_char'),
                func.avg(ChunkDB.generation_time_seconds).label('avg_time_per_chunk'),
                func.avg(ChunkDB.text_end - ChunkDB.text_start).label('avg_text_length')
            ).filter(
                ChunkDB.id.in_(session.query(recent_chunk_ids.c.id))
            ).first()
            
            if untrimmed_result and untrimmed_result.avg_time_per_char and untrimmed_result.avg_time_per_char > 0:
                avg_time_per_char = float(untrimmed_result.avg_time_per_char)
                if untrimmed_result.avg_time_per_chunk:
                    avg_time_per_chunk = float(untrimmed_result.avg_time_per_chunk)
                final_result = untrimmed_result  # Use untrimmed result for avg_text_length
            elif untrimmed_result and untrimmed_result.avg_time_per_chunk:
                # Fallback: calculate from avg_time_per_chunk and avg_text_length
                avg_time_per_chunk = float(untrimmed_result.avg_time_per_chunk)
                if untrimmed_result.avg_text_length and untrimmed_result.avg_text_length > 0:
                    avg_time_per_char = avg_time_per_chunk / float(untrimmed_result.avg_text_length)
                final_result = untrimmed_result  # Use untrimmed result for avg_text_length
        
        # Calculate total characters for pending chunks (SQL aggregate)
        # Simple: query all chunks with status='pending' and sum their text lengths
        total_chars_result = session.query(
            func.sum(ChunkDB.text_end - ChunkDB.text_start).label('total_chars')
        ).filter(
            ChunkDB.status == ChunkStatus.PENDING.value,
            ChunkDB.text_end.isnot(None),
            ChunkDB.text_start.isnot(None)
        ).first()
        
        total_chars = float(total_chars_result.total_chars) if total_chars_result and total_chars_result.total_chars else 0
        
        # If no pending chunks in DB yet, estimate using average text length * number of pending jobs
        if total_chars == 0 and pending_jobs:
            avg_text_len = None
            if final_result and final_result.avg_text_length:
                avg_text_len = float(final_result.avg_text_length)
            
            if avg_text_len:
                total_chars = len(pending_jobs) * avg_text_len
                logger.debug(f"Estimated total_chars from {len(pending_jobs)} jobs * {avg_text_len:.1f} avg_text_length = {total_chars:.0f}")
            else:
                # Fallback: use default average text length (~233 chars)
                total_chars = len(pending_jobs) * 233.0
                logger.debug(f"Estimated total_chars from {len(pending_jobs)} jobs * 233.0 (default) = {total_chars:.0f}")
        
        # Calculate ETA: avg_time_per_char * total_chars
        estimated_seconds_remaining = int(total_chars * avg_time_per_char) if total_chars > 0 else 0
        
        # Log detailed calculation for debugging
        logger.info(
            f"ETA Calculation: avg_time_per_char={avg_time_per_char:.6f}, "
            f"total_chars={total_chars:,.0f}, "
            f"estimated_seconds={estimated_seconds_remaining:,} "
            f"({estimated_seconds_remaining/3600:.2f} hours), "
            f"pending_jobs={len(pending_jobs)}"
        )
        
        return {
            'estimated_seconds_remaining': estimated_seconds_remaining,
            'avg_time_per_chunk': round(avg_time_per_chunk, 2),
            'avg_time_per_char': round(avg_time_per_char, 4),
        }
    
    @staticmethod
    def create_or_update(chunk: Chunk, chapter_number: Optional[int] = None, session: Optional[Session] = None) -> ChunkDB:
        """Create or update a chunk."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.create_or_update(chunk, chapter_number, session)
        
        # Generate chunk ID
        chapter_id = chunk.chapter_id or f"{chunk.book_id}_{chunk.index:02d}"
        chunk_id = f"{chunk.book_id}_{chapter_id}_{chunk.index}"
        
        chunk_db = session.query(ChunkDB).filter(ChunkDB.id == chunk_id).first()
        if chunk_db:
            # Update existing
            chunk_db.text_start = chunk.text_start
            chunk_db.text_end = chunk.text_end
            chunk_db.status = chunk.status.value
            chunk_db.path = chunk.path
            chunk_db.generation_time_seconds = chunk.generation_time_seconds
            chunk_db.audio_duration_seconds = chunk.audio_duration_seconds
            chunk_db.voice_name = chunk.voice_name
            chunk_db.speed = chunk.speed
            chunk_db.pre_pause_ms = chunk.pre_pause_ms
            chunk_db.post_pause_ms = chunk.post_pause_ms
            chunk_db.is_dialogue = chunk.is_dialogue
            chunk_db.is_scene_break = chunk.is_scene_break
        else:
            # Create new
            # Need to get chapter_number from chapter_id or chunk
            chapter_number = 0  # Will be set from chapter relationship
            if chunk.chapter_id:
                # Extract chapter number from chapter_id (format: book_id_XX)
                parts = chunk.chapter_id.split('_')
                if len(parts) >= 2:
                    try:
                        chapter_number = int(parts[-1])
                    except ValueError:
                        pass
            
            # Create new
            chunk_db = ChunkDB(
                id=chunk_id,
                book_id=chunk.book_id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                index=chunk.index,
                text_start=chunk.text_start,
                text_end=chunk.text_end,
                status=chunk.status.value,
                path=chunk.path,
                generation_time_seconds=chunk.generation_time_seconds,
                audio_duration_seconds=chunk.audio_duration_seconds,
                voice_name=chunk.voice_name,
                speed=chunk.speed,
                pre_pause_ms=chunk.pre_pause_ms,
                post_pause_ms=chunk.post_pause_ms,
                is_dialogue=chunk.is_dialogue,
                is_scene_break=chunk.is_scene_break,
            )
            session.add(chunk_db)
        
        return chunk_db
    
    @staticmethod
    def update_status(
        book_id: str, 
        chapter_number: int, 
        chunk_index: int, 
        status: ChunkStatus, 
        error: Optional[str] = None,
        processing_started_at: Optional[datetime] = None,
        session: Optional[Session] = None
    ) -> bool:
        """Update chunk status and related fields (fast update)."""
        if session is None:
            with db_session() as session:
                return ChunkRepository.update_status(
                    book_id, chapter_number, chunk_index, status, error, processing_started_at, session
                )
        
        chunk_db = session.query(ChunkDB).filter(
            and_(
                ChunkDB.book_id == book_id,
                ChunkDB.chapter_number == chapter_number,
                ChunkDB.index == chunk_index
            )
        ).first()
        
        if chunk_db:
            chunk_db.status = status.value
            if error is not None:
                chunk_db.error = error
            if processing_started_at is not None:
                chunk_db.processing_started_at = processing_started_at
            elif status == ChunkStatus.RUNNING and chunk_db.processing_started_at is None:
                # Set processing_started_at when transitioning to RUNNING if not already set
                from datetime import datetime
                chunk_db.processing_started_at = datetime.utcnow()
            elif status in (ChunkStatus.COMPLETED, ChunkStatus.FAILED, ChunkStatus.PENDING):
                # Clear processing_started_at when not running
                chunk_db.processing_started_at = None
            return True
        return False
    
    @staticmethod
    def get_running_chunks(session: Optional[Session] = None) -> List[ChunkDB]:
        """
        Get all chunks with RUNNING status.
        
        Returns raw ChunkDB objects (not domain models) to access DB-only fields
        like processing_started_at and error.
        
        Args:
            session: Optional database session
            
        Returns:
            List of ChunkDB objects with RUNNING status
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_running_chunks(session)
        
        return session.query(ChunkDB).filter(
            ChunkDB.status == ChunkStatus.RUNNING.value
        ).all()
    
    @staticmethod
    def get_chunks_by_status(
        status: ChunkStatus,
        book_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by_updated: bool = False,
        session: Optional[Session] = None
    ) -> List[ChunkDB]:
        """
        Get chunks filtered by status with pagination.
        
        Returns raw ChunkDB objects (not domain models) to access DB-only fields.
        
        Args:
            status: Chunk status to filter by
            book_id: Optional book ID filter
            chapter_number: Optional chapter number filter
            limit: Maximum number of chunks to return
            offset: Offset for pagination
            order_by_updated: If True, order by updated_at DESC; otherwise by book/chapter/index
            session: Optional database session
            
        Returns:
            List of ChunkDB objects matching the criteria
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_chunks_by_status(
                    status, book_id, chapter_number, limit, offset, order_by_updated, session
                )
        
        query = session.query(ChunkDB).filter(ChunkDB.status == status.value)
        
        if book_id:
            query = query.filter(ChunkDB.book_id == book_id)
        if chapter_number is not None:
            query = query.filter(ChunkDB.chapter_number == chapter_number)
        
        if order_by_updated:
            query = query.order_by(ChunkDB.updated_at.desc())
        else:
            query = query.order_by(ChunkDB.book_id, ChunkDB.chapter_number, ChunkDB.index)
        
        if limit is not None:
            query = query.offset(offset).limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_chunk_for_recovery_check(
        book_id: str,
        chapter_number: int,
        chunk_index: int,
        session: Optional[Session] = None
    ) -> Optional[ChunkDB]:
        """
        Get a chunk by book/chapter/index for recovery operations.
        
        Returns raw ChunkDB object to access DB-only fields like status and processing_started_at.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index
            session: Optional database session
            
        Returns:
            ChunkDB object or None if not found
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.get_chunk_for_recovery_check(
                    book_id, chapter_number, chunk_index, session
                )
        
        return session.query(ChunkDB).filter(
            and_(
                ChunkDB.book_id == book_id,
                ChunkDB.chapter_number == chapter_number,
                ChunkDB.index == chunk_index
            )
        ).first()
    
    @staticmethod
    def delete_by_chapter(
        book_id: str,
        chapter_number: int,
        session: Optional[Session] = None
    ) -> int:
        """
        Delete all chunks for a chapter from the database.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            session: Optional database session
            
        Returns:
            Number of chunks deleted
        """
        if session is None:
            with db_session() as session:
                return ChunkRepository.delete_by_chapter(book_id, chapter_number, session)
        
        # Bulk delete all chunks for this chapter
        deleted_count = session.query(ChunkDB).filter(
            and_(
                ChunkDB.book_id == book_id,
                ChunkDB.chapter_number == chapter_number
            )
        ).delete(synchronize_session='fetch')
        
        session.commit()
        return deleted_count
    
    @staticmethod
    def _to_model(chunk_db: ChunkDB) -> Chunk:
        """Convert database model to domain model."""
        # Note: Chunk model doesn't have error or processing_started_at fields
        # These are DB-only fields for tracking job state
        return Chunk(
            index=chunk_db.index,
            book_id=chunk_db.book_id,
            text_start=chunk_db.text_start,
            text_end=chunk_db.text_end,
            status=ChunkStatus(chunk_db.status),
            chapter_id=chunk_db.chapter_id,
            path=chunk_db.path,
            generation_time_seconds=chunk_db.generation_time_seconds,
            audio_duration_seconds=chunk_db.audio_duration_seconds,
            voice_name=chunk_db.voice_name,
            speed=chunk_db.speed,
            pre_pause_ms=chunk_db.pre_pause_ms,
            post_pause_ms=chunk_db.post_pause_ms,
            is_dialogue=chunk_db.is_dialogue,
            is_scene_break=chunk_db.is_scene_break,
        )

