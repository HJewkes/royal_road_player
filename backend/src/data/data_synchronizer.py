"""Data synchronizer for loading and writing book/chapter/chunk data."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.models.book import Book
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class DataSynchronizer:
    """Synchronizes data between filesystem and model objects."""
    
    def __init__(self, books_dir: Optional[Path] = None):
        """
        Initialize data synchronizer.
        
        Args:
            books_dir: Path to books directory (defaults to settings.books_dir)
        """
        self.settings = get_settings()
        self.books_dir = books_dir or self.settings.books_dir
    
    def load_books(self) -> List[Book]:
        """
        Load all books from the database (fallback to filesystem if DB empty).
        
        Returns:
            List of Book instances
        """
        # Try database first
        try:
            from src.data.db_repository import BookRepository
            books = BookRepository.get_all()
            if books:
                logger.debug(f"Loaded {len(books)} books from database")
                return books
        except Exception as e:
            logger.warning(f"Failed to load books from database, falling back to filesystem: {e}")
        
        # Fallback to filesystem
        books = []
        
        if not self.books_dir.exists():
            logger.warning(f"Books directory does not exist: {self.books_dir}")
            return books
        
        for book_dir in self.books_dir.iterdir():
            if not book_dir.is_dir():
                continue
            
            metadata_path = book_dir / "metadata.json"
            if not metadata_path.exists():
                logger.debug(f"Skipping {book_dir.name}: no metadata.json")
                continue
            
            try:
                book = self.load_book(book_dir.name)
                if book:
                    books.append(book)
            except Exception as e:
                logger.error(f"Failed to load book {book_dir.name}: {e}")
        
        return books
    
    def load_book(self, book_id_or_dir: str) -> Optional[Book]:
        """
        Load a single book by ID or directory name.
        
        Tries database first, falls back to filesystem.
        
        Args:
            book_id_or_dir: Book ID or directory name
            
        Returns:
            Book instance or None if not found
        """
        # Try database first
        try:
            from src.data.db_repository import BookRepository
            book = BookRepository.get_by_id(book_id_or_dir)
            if book:
                logger.debug(f"Loaded book {book_id_or_dir} from database")
                return book
        except Exception as e:
            logger.debug(f"Book {book_id_or_dir} not in database, trying filesystem: {e}")
        
        # Fallback to filesystem
        book_dir = None
        
        # Try exact match first (fast path)
        potential_dir = self.books_dir / book_id_or_dir
        if potential_dir.exists() and potential_dir.is_dir():
            book_dir = potential_dir
        else:
            # Try common pattern: directory name contains book_id
            book_id_lower = book_id_or_dir.lower()
            for dir_path in self.books_dir.iterdir():
                if not dir_path.is_dir():
                    continue
                if book_id_lower in dir_path.name.lower():
                    metadata_path = dir_path / "metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            if metadata.get('book_id') == book_id_or_dir:
                                book_dir = dir_path
                                break
                        except Exception:
                            continue
        
        if book_dir is None:
            return None
        
        metadata_path = book_dir / "metadata.json"
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            book = Book(
                id=metadata.get('book_id', ''),
                title=metadata.get('book_title', ''),
                author=metadata.get('author'),
                url=metadata.get('book_url'),
                filter_book_number=metadata.get('filter_book_number'),
                path=str(book_dir),
            )
            
            # Save to database for next time
            try:
                from src.data.db_repository import BookRepository
                BookRepository.create_or_update(book)
            except Exception as e:
                logger.debug(f"Failed to save book to database: {e}")
            
            return book
        except Exception as e:
            logger.error(f"Failed to load book from {metadata_path}: {e}")
            return None
    
    def load_chapters(self, book_id: str) -> List[Chapter]:
        """
        Load all chapters for a book.
        
        Tries database first, falls back to filesystem.
        
        Args:
            book_id: Book ID
            
        Returns:
            List of Chapter instances
        """
        # Try database first
        try:
            from src.data.db_repository import ChapterRepository
            chapters = ChapterRepository.get_by_book(book_id)
            if chapters:
                logger.debug(f"Loaded {len(chapters)} chapters for book {book_id} from database")
                return chapters
        except Exception as e:
            logger.debug(f"Chapters for book {book_id} not in database, trying filesystem: {e}")
        
        # Fallback to filesystem
        book = self.load_book(book_id)
        if book is None or book.path is None:
            return []
        
        chapters = []
        chapters_dir = Path(book.path) / "chapters"
        
        if not chapters_dir.exists():
            return chapters
        
        # Load chapters from numbered directories
        for chapter_dir in sorted(chapters_dir.iterdir(), key=lambda x: int(x.name) if x.name.isdigit() else 999):
            if not chapter_dir.is_dir():
                continue
            
            # Skip non-numeric directories (shouldn't happen, but be safe)
            if not chapter_dir.name.isdigit():
                continue
            
            try:
                chapter = self.load_chapter(book_id, int(chapter_dir.name), book_path=book.path)
                if chapter:
                    chapters.append(chapter)
                    # Save to database for next time
                    try:
                        from src.data.db_repository import ChapterRepository
                        ChapterRepository.create_or_update(chapter)
                    except Exception as e:
                        logger.debug(f"Failed to save chapter to database: {e}")
            except Exception as e:
                logger.error(f"Failed to load chapter {chapter_dir.name} for book {book_id}: {e}")
        
        return chapters
    
    def load_chapter(self, book_id: str, chapter_number: int, book_path: Optional[str] = None) -> Optional[Chapter]:
        """
        Load a single chapter by book ID and chapter number.
        
        Args:
            book_id: Book ID
            chapter_number: Chapter number
            book_path: Optional book path to avoid reloading book metadata
            
        Returns:
            Chapter instance or None if not found
        """
        if book_path is None:
            book = self.load_book(book_id)
            if book is None or book.path is None:
                return None
            book_path = book.path
        else:
            # Verify path exists
            if not Path(book_path).exists():
                return None
        
        chapter_dir = Path(book_path) / "chapters" / f"{chapter_number:02d}"
        metadata_path = chapter_dir / "metadata.json"
        
        # If metadata.json doesn't exist, try to create chapter from directory structure
        if not metadata_path.exists():
            # Chapter directory exists but no metadata - create basic chapter
            if chapter_dir.exists():
                logger.debug(f"Chapter {chapter_number} directory exists but no metadata.json, creating basic chapter")
                # Create a basic chapter with minimal metadata
                chapter = Chapter(
                    id=f"{book_id}_{chapter_number:02d}",
                    book_id=book_id,
                    chapter_number=chapter_number,
                    number=None,
                    title=f"Chapter {chapter_number}",
                    url=None,
                    path=str(chapter_dir),
                )
                # Save it so it exists next time
                self.save_chapter(chapter)
                return chapter
            return None
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            return Chapter(
                id=metadata.get('id'),
                book_id=metadata.get('book_id', book_id),
                chapter_number=metadata.get('chapter_number'),
                number=metadata.get('number'),  # Royal Road number
                title=metadata.get('title', ''),
                url=metadata.get('url'),
                path=str(chapter_dir),
            )
        except Exception as e:
            logger.error(f"Failed to load chapter from {metadata_path}: {e}")
            return None
    
    def load_chunks(self, book_id: str, chapter_number: int) -> List[Chunk]:
        """
        Load all chunks for a chapter.
        
        Tries database first, falls back to filesystem.
        
        Args:
            book_id: Book ID
            chapter_number: Chapter number
            
        Returns:
            List of Chunk instances
        """
        # Try database first
        try:
            from src.data.db_repository import ChunkRepository
            chunks = ChunkRepository.get_by_chapter(book_id, chapter_number)
            if chunks:
                logger.debug(f"Loaded {len(chunks)} chunks for chapter {chapter_number} from database")
                return chunks
        except Exception as e:
            logger.debug(f"Chunks for chapter {chapter_number} not in database, trying filesystem: {e}")
        
        # Fallback to filesystem
        chapter = self.load_chapter(book_id, chapter_number)
        if chapter is None or chapter.path is None:
            return []
        
        chunks = []
        chunks_dir = Path(chapter.path) / "chunks"
        
        if not chunks_dir.exists():
            return chunks
        
        # Load chunks from numbered directories
        for chunk_dir in sorted(chunks_dir.iterdir(), key=lambda x: int(x.name) if x.name.isdigit() else 999):
            if not chunk_dir.is_dir():
                continue
            
            if not chunk_dir.name.isdigit():
                continue
            
            try:
                chunk = self.load_chunk(book_id, chapter_number, int(chunk_dir.name))
                if chunk:
                    chunks.append(chunk)
                    # Save to database for next time
                    try:
                        from src.data.db_repository import ChunkRepository
                        ChunkRepository.create_or_update(chunk, chapter_number)
                    except Exception as e:
                        logger.debug(f"Failed to save chunk to database: {e}")
            except Exception as e:
                logger.error(f"Failed to load chunk {chunk_dir.name} for chapter {chapter_number}: {e}")
        
        return chunks
    
    def load_chunk(self, book_id: str, chapter_number: int, chunk_index: int) -> Optional[Chunk]:
        """
        Load a single chunk by book ID, chapter number, and chunk index.
        
        Args:
            book_id: Book ID
            chapter_number: Chapter number
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk instance or None if not found
        """
        chapter = self.load_chapter(book_id, chapter_number)
        if chapter is None or chapter.path is None:
            return None
        
        chunk_dir = Path(chapter.path) / "chunks" / str(chunk_index)
        metadata_path = chunk_dir / "metadata.json"
        
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Parse status string to ChunkStatus enum
            status_str = metadata.get('status', 'pending')
            try:
                status = ChunkStatus(status_str)
            except ValueError:
                logger.warning(f"Invalid chunk status '{status_str}', defaulting to pending")
                status = ChunkStatus.PENDING
            
            # Get chapter ID from chapter if available
            chapter_id = None
            if chapter.id:
                chapter_id = chapter.id
            
            # Load synthesis metadata fields (backward compatible with old 'synthesis' dict)
            synthesis_data = metadata.get('synthesis', {}) if isinstance(metadata.get('synthesis'), dict) else {}
            
            return Chunk(
                index=metadata.get('index', chunk_index),
                book_id=metadata.get('book_id', book_id),
                text_start=metadata.get('text_start', 0),
                text_end=metadata.get('text_end', 0),
                status=status,
                chapter_id=metadata.get('chapter_id') or chapter_id,
                path=str(chunk_dir),
                audio_duration_seconds=metadata.get('audio_duration_seconds'),
                generation_time_seconds=metadata.get('generation_time_seconds'),
                # Synthesis parameters (from 'synthesis' dict or top-level fields)
                voice_name=metadata.get('voice_name') or synthesis_data.get('voice_name'),
                speed=metadata.get('speed') if 'speed' in metadata else synthesis_data.get('speed'),
                pre_pause_ms=metadata.get('pre_pause_ms', synthesis_data.get('pre_pause_ms', 0)),
                post_pause_ms=metadata.get('post_pause_ms', synthesis_data.get('post_pause_ms', 0)),
                is_dialogue=metadata.get('is_dialogue', synthesis_data.get('is_dialogue', False)),
                is_scene_break=metadata.get('is_scene_break', synthesis_data.get('is_scene_break', False)),
            )
        except Exception as e:
            logger.error(f"Failed to load chunk from {metadata_path}: {e}")
            return None
    
    def save_book(self, book: Book) -> None:
        """
        Save book metadata to database and filesystem.
        
        Args:
            book: Book instance to save
        """
        # Save to database first
        try:
            from src.data.db_repository import BookRepository
            BookRepository.create_or_update(book)
            logger.debug(f"Saved book to database: {book.id}")
        except Exception as e:
            logger.warning(f"Failed to save book to database: {e}")
        
        # Also save to filesystem for backward compatibility
        if book.path is None:
            raise ValueError("Book path is required")
        
        book_dir = Path(book.path)
        book_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_path = book_dir / "metadata.json"
        metadata = {
            'book_id': book.id,
            'book_title': book.title,
            'author': book.author,
            'book_url': book.url,
            'filter_book_number': book.filter_book_number,
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved book metadata: {book.id}")
    
    def save_chapter(self, chapter: Chapter) -> None:
        """
        Save chapter metadata to database and filesystem.
        
        Args:
            chapter: Chapter instance to save
        """
        # Save to database first
        try:
            from src.data.db_repository import ChapterRepository
            ChapterRepository.create_or_update(chapter)
            logger.debug(f"Saved chapter to database: {chapter.id}")
        except Exception as e:
            logger.warning(f"Failed to save chapter to database: {e}")
        
        # Also save to filesystem for backward compatibility
        if chapter.path is None:
            raise ValueError("Chapter path is required")
        
        chapter_dir = Path(chapter.path)
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_path = chapter_dir / "metadata.json"
        metadata = {
            'id': chapter.id,
            'book_id': chapter.book_id,
            'chapter_number': chapter.chapter_number,
            'number': chapter.number,  # Royal Road number
            'title': chapter.title,
            'url': chapter.url,
            'word_count': chapter.text_size,  # Use computed text_size
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved chapter metadata: {chapter.book_id}/{chapter.chapter_number}")
    
    def save_chunk(self, chunk: Chunk, chapter_number: Optional[int] = None) -> None:
        """
        Save chunk metadata to database and filesystem.
        
        Args:
            chunk: Chunk instance to save
            chapter_number: Chapter number (extracted from chunk.chapter_id if not provided)
        """
        # Extract chapter_number from chunk.chapter_id if not provided
        if chapter_number is None and chunk.chapter_id:
            parts = chunk.chapter_id.split('_')
            if len(parts) >= 2:
                try:
                    chapter_number = int(parts[-1])
                except ValueError:
                    pass
        
        # Save to database first
        try:
            from src.data.db_repository import ChunkRepository
            ChunkRepository.create_or_update(chunk, chapter_number)
            logger.debug(f"Saved chunk to database: {chunk.book_id}/{chunk.index}")
        except Exception as e:
            logger.warning(f"Failed to save chunk to database: {e}")
        
        # Also save to filesystem for backward compatibility
        if chunk.path is None:
            raise ValueError("Chunk path is required")
        
        chunk_dir = Path(chunk.path)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_path = chunk_dir / "metadata.json"
        metadata = {
            'index': chunk.index,
            'book_id': chunk.book_id,
            'chapter_id': chunk.chapter_id,
            'text_start': chunk.text_start,
            'text_end': chunk.text_end,
            'status': chunk.status.value,  # Convert enum to string
            'generation_time_seconds': chunk.generation_time_seconds,
            'audio_duration_seconds': chunk.audio_duration_seconds,
            # Synthesis parameters
            'voice_name': chunk.voice_name,
            'speed': chunk.speed,
            'pre_pause_ms': chunk.pre_pause_ms,
            'post_pause_ms': chunk.post_pause_ms,
            'is_dialogue': chunk.is_dialogue,
            'is_scene_break': chunk.is_scene_break,
        }
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                f.flush()  # Ensure data is written to disk
                import os
                os.fsync(f.fileno())  # Force write to disk
            logger.info(f"Saved chunk metadata: {chunk.book_id}/{chunk.index} (status={chunk.status.value})")
        except Exception as e:
            logger.error(f"Failed to save chunk metadata to {metadata_path}: {e}", exc_info=True)
            raise
    
    def update_chunk_status(self, book_id: str, chapter_number: int, chunk_index: int, status: ChunkStatus) -> Optional[Chunk]:
        """
        Update chunk status and save to filesystem.
        
        Args:
            book_id: Book ID
            chapter_number: Chapter number
            chunk_index: Chunk index
            status: New status
            
        Returns:
            Updated Chunk instance or None if not found
        """
        chunk = self.load_chunk(book_id, chapter_number, chunk_index)
        if chunk is None:
            return None
        
        # Create updated chunk with new status (models are frozen, so create new instance)
        updated_chunk = Chunk(
            index=chunk.index,
            book_id=chunk.book_id,
            text_start=chunk.text_start,
            text_end=chunk.text_end,
            status=status,
            chapter_id=chunk.chapter_id,
            path=chunk.path,
            generation_time_seconds=chunk.generation_time_seconds,
            voice_name=chunk.voice_name,
            speed=chunk.speed,
            pre_pause_ms=chunk.pre_pause_ms,
            post_pause_ms=chunk.post_pause_ms,
            is_dialogue=chunk.is_dialogue,
            is_scene_break=chunk.is_scene_break,
        )
        
        self.save_chunk(updated_chunk, chapter_number)
        return updated_chunk

