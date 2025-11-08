"""Controller for chunking operations (multi-chunk operations)."""

import logging
from pathlib import Path
from typing import List, Optional

from src.data.data_synchronizer import DataSynchronizer
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.models.responses import ChunkingResult
from src.tts.chunker import chunk_text_by_paragraphs
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
        Chunk a chapter's text into segments.
        
        This creates chunk metadata and saves chunk text files but does NOT generate audio.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            Dictionary with chunking results
            
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
        
        text_content = text_file.read_text(encoding='utf-8')
        
        # Calculate chunking parameters
        if target_chars is None:
            target_chars = int(chunk_duration_minutes * 800)  # ~800 chars per minute
        
        if min_chars is None:
            min_chars = int(target_chars * 0.3)  # At least 30% of target
        
        if max_chars is None:
            max_chars = min(int(target_chars * 1.5), 250)  # Cap at 250 for XTTS v2
        
        # Chunk the text
        logger.info(f"Chunking text with target={target_chars}, min={min_chars}, max={max_chars}")
        chunk_data = chunk_text_by_paragraphs(
            text_content,
            target_chars_per_minute=target_chars,
            min_chars=min_chars,
            max_chars=max_chars,
            return_positions=True,
        )
        
        # Create chunk directories and save text files
        chunks_dir = chapter.chunks_dir
        if chunks_dir is None:
            raise ValueError("Chapter chunks directory path is None")
        
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        chunks = []
        for i, chunk_info in enumerate(chunk_data, 1):
            if isinstance(chunk_info, tuple):
                chunk_text, start_pos, end_pos = chunk_info
            else:
                chunk_text = chunk_info
                start_pos = text_content.find(chunk_text)
                end_pos = start_pos + len(chunk_text) if start_pos >= 0 else len(chunk_text)
            
            # Create chunk directory
            chunk_dir = chunks_dir / str(i)
            chunk_dir.mkdir(parents=True, exist_ok=True)
            
            # Save chunk text file
            chunk_text_path = chunk_dir / "text.txt"
            chunk_text_path.write_text(chunk_text, encoding='utf-8')
            
            # Create chunk model
            chunk = Chunk(
                index=i,
                book_id=book_id,
                text_start=start_pos,
                text_end=end_pos,
                status=ChunkStatus.PENDING,
                chapter_id=chapter.id,
                path=str(chunk_dir),
            )
            
            # Save chunk metadata
            self.sync.save_chunk(chunk)
            chunks.append(chunk)
        
        # Adjust chunk end positions to eliminate gaps
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            if current_chunk.text_end < next_chunk.text_start:
                # Update current chunk to extend to next chunk start
                updated_chunk = Chunk(
                    index=current_chunk.index,
                    book_id=current_chunk.book_id,
                    text_start=current_chunk.text_start,
                    text_end=next_chunk.text_start,
                    status=current_chunk.status,
                    chapter_id=current_chunk.chapter_id,
                    path=current_chunk.path,
                    generation_time_seconds=current_chunk.generation_time_seconds,
                    flagged=current_chunk.flagged,
                )
                self.sync.save_chunk(updated_chunk)
                chunks[i] = updated_chunk
        
        logger.info(f"✅ Created {len(chunks)} chunks for chapter {chapter_number}")
        
        return ChunkingResult(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_count=len(chunks),
            total_text_length=len(text_content),
        )

