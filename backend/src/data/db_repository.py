"""Database repository for CRUD operations."""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, desc

from src.data.database import get_session
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
            session = get_session()
            try:
                return BookRepository.get_all(session)
            finally:
                session.close()
        
        books = session.query(BookDB).all()
        return [BookRepository._to_model(book) for book in books]
    
    @staticmethod
    def get_by_id(book_id: str, session: Optional[Session] = None) -> Optional[Book]:
        """Get book by ID."""
        if session is None:
            session = get_session()
            try:
                return BookRepository.get_by_id(book_id, session)
            finally:
                session.close()
        
        book_db = session.query(BookDB).filter(BookDB.id == book_id).first()
        return BookRepository._to_model(book_db) if book_db else None
    
    @staticmethod
    def get_by_path(path: str, session: Optional[Session] = None) -> Optional[Book]:
        """Get book by path."""
        if session is None:
            session = get_session()
            try:
                return BookRepository.get_by_path(path, session)
            finally:
                session.close()
        
        book_db = session.query(BookDB).filter(BookDB.path == path).first()
        return BookRepository._to_model(book_db) if book_db else None
    
    @staticmethod
    def create_or_update(book: Book, session: Optional[Session] = None) -> BookDB:
        """Create or update a book."""
        if session is None:
            session = get_session()
            try:
                result = BookRepository.create_or_update(book, session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
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
            session = get_session()
            try:
                return ChapterRepository.get_by_book(book_id, session)
            finally:
                session.close()
        
        chapters = session.query(ChapterDB).filter(ChapterDB.book_id == book_id).order_by(ChapterDB.chapter_number).all()
        return [ChapterRepository._to_model(ch) for ch in chapters]
    
    @staticmethod
    def get_by_id(chapter_id: str, session: Optional[Session] = None) -> Optional[Chapter]:
        """Get chapter by ID."""
        if session is None:
            session = get_session()
            try:
                return ChapterRepository.get_by_id(chapter_id, session)
            finally:
                session.close()
        
        chapter_db = session.query(ChapterDB).filter(ChapterDB.id == chapter_id).first()
        return ChapterRepository._to_model(chapter_db) if chapter_db else None
    
    @staticmethod
    def get_by_book_and_number(book_id: str, chapter_number: int, session: Optional[Session] = None) -> Optional[Chapter]:
        """Get chapter by book ID and chapter number."""
        if session is None:
            session = get_session()
            try:
                return ChapterRepository.get_by_book_and_number(book_id, chapter_number, session)
            finally:
                session.close()
        
        chapter_db = session.query(ChapterDB).filter(
            and_(ChapterDB.book_id == book_id, ChapterDB.chapter_number == chapter_number)
        ).first()
        return ChapterRepository._to_model(chapter_db) if chapter_db else None
    
    @staticmethod
    def create_or_update(chapter: Chapter, session: Optional[Session] = None) -> ChapterDB:
        """Create or update a chapter."""
        if session is None:
            session = get_session()
            try:
                result = ChapterRepository.create_or_update(chapter, session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
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
            session = get_session()
            try:
                return ChunkRepository.get_by_chapter(book_id, chapter_number, session)
            finally:
                session.close()
        
        chunks = session.query(ChunkDB).filter(
            and_(ChunkDB.book_id == book_id, ChunkDB.chapter_number == chapter_number)
        ).order_by(ChunkDB.index).all()
        return [ChunkRepository._to_model(ch) for ch in chunks]
    
    @staticmethod
    def get_by_id(chunk_id: str, session: Optional[Session] = None) -> Optional[Chunk]:
        """Get chunk by ID."""
        if session is None:
            session = get_session()
            try:
                return ChunkRepository.get_by_id(chunk_id, session)
            finally:
                session.close()
        
        chunk_db = session.query(ChunkDB).filter(ChunkDB.id == chunk_id).first()
        return ChunkRepository._to_model(chunk_db) if chunk_db else None
    
    @staticmethod
    def get_by_book_chapter_index(book_id: str, chapter_number: int, chunk_index: int, session: Optional[Session] = None) -> Optional[Chunk]:
        """Get chunk by book, chapter, and index."""
        if session is None:
            session = get_session()
            try:
                return ChunkRepository.get_by_book_chapter_index(book_id, chapter_number, chunk_index, session)
            finally:
                session.close()
        
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
            session = get_session()
            try:
                return ChunkRepository.count_by_status(book_id, chapter_number, status, session)
            finally:
                session.close()
        
        query = session.query(func.count(ChunkDB.id)).filter(ChunkDB.status == status.value)
        
        if book_id:
            query = query.filter(ChunkDB.book_id == book_id)
        if chapter_number is not None:
            query = query.filter(ChunkDB.chapter_number == chapter_number)
        
        return query.scalar() or 0
    
    @staticmethod
    def get_pending_chunks_ordered(limit: int = 10, session: Optional[Session] = None) -> List[tuple]:
        """
        Get pending chunks ordered by book_id, chapter_number, chunk_index (earliest first).
        Efficient SQL query for job queue processing.
        
        Args:
            limit: Maximum number of chunks to return
            session: Optional database session
            
        Returns:
            List of (Chunk, chapter_number) tuples ordered by book/chapter/index
        """
        if session is None:
            session = get_session()
            try:
                return ChunkRepository.get_pending_chunks_ordered(limit, session)
            finally:
                session.close()
        
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
        Calculate ETA for pending jobs using SQL queries.
        
        Simple approach: Get average time per chunk from recent completed chunks,
        multiply by number of pending jobs. No need to query each pending chunk.
        
        Args:
            pending_jobs: List of (book_id, chapter_number, chunk_index) tuples for pending jobs
            session: Optional database session
            
        Returns:
            Dictionary with 'estimated_seconds_remaining', 'avg_time_per_chunk', 'avg_time_per_char'
        """
        if session is None:
            session = get_session()
            try:
                return ChunkRepository.calculate_eta(pending_jobs, session)
            finally:
                session.close()
        
        # Default fallbacks
        avg_time_per_chunk = 7.0
        avg_time_per_char = 0.03
        
        if not pending_jobs:
            return {
                'estimated_seconds_remaining': 0,
                'avg_time_per_chunk': avg_time_per_chunk,
                'avg_time_per_char': avg_time_per_char,
            }
        
        # Get recent completed chunk IDs (last 50) for calculating averages
        recent_completed_ids = session.query(ChunkDB.id).filter(
            ChunkDB.status == ChunkStatus.COMPLETED.value,
            ChunkDB.generation_time_seconds.isnot(None),
            ChunkDB.generation_time_seconds > 0,
            ChunkDB.text_end.isnot(None),
            ChunkDB.text_start.isnot(None),
            (ChunkDB.text_end - ChunkDB.text_start) > 0  # Avoid division by zero
        ).order_by(desc(ChunkDB.updated_at)).limit(50).subquery()
        
        # Calculate average time per character from recent completed chunks (SQL aggregate)
        result = session.query(
            func.avg(ChunkDB.generation_time_seconds / (ChunkDB.text_end - ChunkDB.text_start)).label('avg_time_per_char'),
            func.avg(ChunkDB.generation_time_seconds).label('avg_time_per_chunk'),
            func.avg(ChunkDB.text_end - ChunkDB.text_start).label('avg_text_length')
        ).filter(
            ChunkDB.id.in_(session.query(recent_completed_ids.c.id))
        ).first()
        
        if result and result.avg_time_per_char and result.avg_time_per_char > 0:
            avg_time_per_char = float(result.avg_time_per_char)
            if result.avg_time_per_chunk:
                avg_time_per_chunk = float(result.avg_time_per_chunk)
        elif result and result.avg_time_per_chunk:
            # Fallback: calculate from avg_time_per_chunk and avg_text_length
            avg_time_per_chunk = float(result.avg_time_per_chunk)
            if result.avg_text_length and result.avg_text_length > 0:
                avg_time_per_char = avg_time_per_chunk / float(result.avg_text_length)
        
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
            if result and result.avg_text_length:
                total_chars = len(pending_jobs) * float(result.avg_text_length)
            else:
                # Fallback: use default average text length (~233 chars)
                total_chars = len(pending_jobs) * 233.0
        
        # Calculate ETA: avg_time_per_char * total_chars
        estimated_seconds_remaining = int(total_chars * avg_time_per_char) if total_chars > 0 else 0
        
        return {
            'estimated_seconds_remaining': estimated_seconds_remaining,
            'avg_time_per_chunk': round(avg_time_per_chunk, 2),
            'avg_time_per_char': round(avg_time_per_char, 4),
        }
    
    @staticmethod
    def create_or_update(chunk: Chunk, chapter_number: Optional[int] = None, session: Optional[Session] = None) -> ChunkDB:
        """Create or update a chunk."""
        if session is None:
            session = get_session()
            try:
                result = ChunkRepository.create_or_update(chunk, chapter_number, session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
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
            session = get_session()
            try:
                result = ChunkRepository.update_status(
                    book_id, chapter_number, chunk_index, status, error, processing_started_at, session
                )
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
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

