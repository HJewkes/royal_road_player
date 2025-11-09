"""Controller for chunking operations (multi-chunk operations)."""

import logging
import shutil
from pathlib import Path
from typing import List, Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import ChunkingResult
from src.text_processing.chunker import TextChunker
from src.text_processing.processor import UnifiedTextProcessor, ProcessingConfig
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class ChunkingController:
    """Controller for chunking chapter text into segments."""
    
    def __init__(self, synchronizer: Optional[DataSynchronizer] = None):
        """
        Initialize chunking controller.
        
        Args:
            synchronizer: Optional DataSynchronizer instance (creates new one if not provided)
        """
        self.settings = get_settings()
        self.sync = synchronizer or DataSynchronizer(books_dir=self.settings.books_dir)
    
    def create_chunks(
        self,
        normalized_text: str,
        book_id: str,
        chapter_id: str,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Create chunks from normalized text in memory (does not save to disk).
        
        Args:
            normalized_text: Already-normalized text content to chunk
            book_id: Book identifier
            chapter_id: Chapter identifier
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            List of Chunk objects with positions relative to normalized_text
        """
        # Calculate chunking parameters
        # Target: ~800 chars per minute of audio, but we want larger chunks for efficiency
        # With XTTS v2 limit of 250 chars, we aim to fill chunks up to the limit
        if target_chars is None:
            target_chars = int(chunk_duration_minutes * 800)  # ~800 chars per minute
            # Use max_chars as target to optimize TTS usage (fill chunks to limit)
            # The chunker will merge short paragraphs to fill up to max_chars
            target_chars = max_chars if max_chars else 250
        
        if min_chars is None:
            min_chars = 50  # Minimum reasonable chunk size
        
        if max_chars is None:
            max_chars = 250  # XTTS v2 hard limit
        
        # Chunk the normalized text
        logger.info(f"Chunking normalized text with target={target_chars}, min={min_chars}, max={max_chars}")
        chunker = TextChunker()
        chunks = chunker.chunk_by_paragraphs(
            normalized_text,
            target_chars_per_minute=target_chars,  # This is actually target_chars, not per minute
            min_chars=min_chars,
            max_chars=max_chars,
            book_id=book_id,
            chapter_id=chapter_id,
        )
        
        logger.info(f"✅ Created {len(chunks)} chunks in memory")
        
        return chunks
    
    def save_chunks(self, chunks: List[Chunk], chapter: Chapter, normalized_text: str) -> None:
        """
        Save chunks to disk.
        
        Args:
            chunks: List of Chunk objects to save
            chapter: Chapter object (for getting chunks directory)
            normalized_text: Normalized text content (positions in chunks are relative to this)
        """
        chunks_dir = chapter.chunks_dir
        if chunks_dir is None:
            raise ValueError("Chapter chunks directory path is None")
        
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        for chunk in chunks:
            # Create chunk directory
            chunk_dir = chunks_dir / str(chunk.index)
            chunk_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract chunk text from normalized text (positions are relative to normalized text)
            chunk_text = normalized_text[chunk.text_start:chunk.text_end]
            
            # Save chunk text file
            chunk_text_path = chunk_dir / "text.txt"
            chunk_text_path.write_text(chunk_text, encoding='utf-8')
            
            # Update chunk with path
            chunk_with_path = Chunk(
                index=chunk.index,
                book_id=chunk.book_id,
                text_start=chunk.text_start,
                text_end=chunk.text_end,
                status=chunk.status,
                chapter_id=chunk.chapter_id,
                path=str(chunk_dir),
                generation_time_seconds=chunk.generation_time_seconds,
                voice_name=chunk.voice_name,
                speed=chunk.speed,
                pre_pause_ms=chunk.pre_pause_ms,
                post_pause_ms=chunk.post_pause_ms,
                is_dialogue=chunk.is_dialogue,
                is_scene_break=chunk.is_scene_break,
            )
            
            # Save chunk metadata
            self.sync.save_chunk(chunk_with_path, chapter.chapter_number)
    
    def chunk_chapter(
        self,
        book_id: str,
        chapter_number: int,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> ChunkingResult:
        """
        Chunk a chapter's text into segments and save to disk.
        
        This creates chunk metadata and saves chunk text files but does NOT generate audio.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            ChunkingResult with chunks included
            
        Raises:
            ValueError: If book or chapter not found
            FileNotFoundError: If chapter text file not found
        """
        # Load chapter
        chapter = self.sync.load_chapter(book_id, chapter_number)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_number} not found for book {book_id}")
        
        if not chapter.has_text:
            raise FileNotFoundError(f"Chapter text file not found: {chapter.text_path}")
        
        # Read text
        text_file = chapter.text_path
        if text_file is None:
            raise FileNotFoundError("Chapter text path is None")
        
        raw_text = text_file.read_text(encoding='utf-8')
        
        # Normalize text first (needed for both creating chunks and saving)
        config = ProcessingConfig(
            extract_html=False,
            normalize_punctuation=True,
            normalize_acronyms=True,
            normalize_numbers=True,
            normalize_dates=True,
            segment_into_breath_groups=False,
            chunk_for_tts=False,
        )
        processor = UnifiedTextProcessor()
        normalized_text = processor.process_text(raw_text, config)
        if isinstance(normalized_text, list):
            normalized_text = '\n\n'.join(normalized_text)
        
        # Create chunks in memory (using normalized text)
        chunks = self.create_chunks(
            normalized_text=normalized_text,
            book_id=book_id,
            chapter_id=chapter.id or f"{book_id}_{chapter_number}",
            chunk_duration_minutes=chunk_duration_minutes,
            target_chars=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        
        # Save chunks to disk (using normalized text for position extraction)
        self.save_chunks(chunks, chapter, normalized_text)
        
        # Reload chunks with paths
        saved_chunks = self.sync.load_chunks(book_id, chapter_number)
        
        logger.info(f"✅ Created and saved {len(saved_chunks)} chunks for chapter {chapter_number}")
        
        return ChunkingResult(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_count=len(saved_chunks),
            total_text_length=len(raw_text),
            chunks=saved_chunks,
        )
    
    def clear_chunks_and_audio(
        self,
        book_id: str,
        chapter_number: int,
    ) -> None:
        """
        Clear all chunks and audio files for a chapter.
        
        This removes:
        - All chunk directories (and their contents including audio.wav files)
        - Chunk metadata files
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Raises:
            ValueError: If chapter not found
        """
        # Load chapter
        chapter = self.sync.load_chapter(book_id, chapter_number)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_number} not found for book {book_id}")
        
        chunks_dir = chapter.chunks_dir
        if chunks_dir is None:
            logger.warning(f"No chunks directory for chapter {chapter_number}, nothing to clear")
            return
        
        if not chunks_dir.exists():
            logger.info(f"Chunks directory does not exist: {chunks_dir}, nothing to clear")
            return
        
        # Delete all chunk directories
        chunk_dirs_removed = 0
        audio_files_removed = 0
        
        for chunk_dir in chunks_dir.iterdir():
            if chunk_dir.is_dir() and chunk_dir.name.isdigit():
                # Count audio files before removal
                audio_file = chunk_dir / "audio.wav"
                if audio_file.exists():
                    audio_files_removed += 1
                
                # Remove entire chunk directory (includes text.txt, audio.wav, metadata.json)
                try:
                    shutil.rmtree(chunk_dir)
                    chunk_dirs_removed += 1
                    logger.debug(f"Removed chunk directory: {chunk_dir}")
                except Exception as e:
                    logger.error(f"Failed to remove chunk directory {chunk_dir}: {e}")
        
        logger.info(
            f"✅ Cleared {chunk_dirs_removed} chunks and {audio_files_removed} audio files "
            f"for chapter {chapter_number}"
        )
    
    def delete_chunk(
        self,
        book_id: str,
        chapter_number: int,
        chunk_index: int,
    ) -> bool:
        """
        Delete a single chunk by index.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_index: Chunk index to delete
            
        Returns:
            True if chunk was deleted, False if not found
            
        Raises:
            ValueError: If chapter not found
        """
        # Load chapter
        chapter = self.sync.load_chapter(book_id, chapter_number)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_number} not found for book {book_id}")
        
        chunks_dir = chapter.chunks_dir
        if chunks_dir is None or not chunks_dir.exists():
            logger.warning(f"No chunks directory for chapter {chapter_number}")
            return False
        
        chunk_dir = chunks_dir / str(chunk_index)
        if not chunk_dir.exists():
            logger.warning(f"Chunk {chunk_index} directory does not exist")
            return False
        
        # Delete chunk directory
        try:
            shutil.rmtree(chunk_dir)
            logger.info(f"✅ Deleted chunk {chunk_index} for chapter {chapter_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_index}: {e}")
            return False
    
    def cleanup_small_failed_chunks(
        self,
        book_id: str,
        chapter_number: int,
    ) -> int:
        """
        Delete failed chunks that are purely whitespace.
        
        This is useful for cleaning up chunks created before the filtering logic
        was added, without having to rebuild all chunks.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            
        Returns:
            Number of chunks deleted
            
        Raises:
            ValueError: If chapter not found
        """
        chunks = self.sync.load_chunks(book_id, chapter_number)
        deleted_count = 0
        
        for chunk in chunks:
            # Only delete failed chunks that are purely whitespace
            if chunk.status != ChunkStatus.FAILED:
                continue
            
            if chunk.path is None:
                continue
            
            chunk_dir = Path(chunk.path)
            if not chunk_dir.exists():
                continue
            
            # Check chunk text content
            text_file = chunk_dir / "text.txt"
            if not text_file.exists():
                continue
            
            chunk_text = text_file.read_text(encoding='utf-8')
            
            # Check if chunk is purely whitespace
            if not chunk_text.strip():
                # Delete this pure whitespace failed chunk
                try:
                    shutil.rmtree(chunk_dir)
                    logger.info(
                        f"Deleted pure whitespace failed chunk {chunk.index} "
                        f"({len(chunk_text)} chars: {repr(chunk_text[:50])})"
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete chunk {chunk.index}: {e}")
        
        if deleted_count > 0:
            logger.info(f"✅ Cleaned up {deleted_count} pure whitespace failed chunks for chapter {chapter_number}")
        
        return deleted_count
    
    def rechunk_chapter(
        self,
        book_id: str,
        chapter_number: int,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> ChunkingResult:
        """
        Rechunk a chapter by clearing old chunks/audio and creating new ones.
        
        This is equivalent to calling clear_chunks_and_audio() followed by chunk_chapter().
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            ChunkingResult with new chunks included
            
        Raises:
            ValueError: If book or chapter not found
            FileNotFoundError: If chapter text file not found
        """
        logger.info(f"Rechunking chapter {chapter_number} for book {book_id}")
        
        # Clear existing chunks and audio
        self.clear_chunks_and_audio(book_id, chapter_number)
        
        # Create new chunks
        return self.chunk_chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_duration_minutes=chunk_duration_minutes,
            target_chars=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
        )

