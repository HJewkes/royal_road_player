"""Service for chunking chapter text into segments."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.tts.chunker import chunk_text_by_paragraphs
from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking chapter text into segments for TTS processing."""
    
    def __init__(self):
        """Initialize chunking service."""
        self.settings = get_settings()
    
    def find_book_dir(self, book_id: str) -> Optional[Path]:
        """
        Find book directory by book_id.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Path to book directory or None if not found
        """
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    import json
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            return dir_path
                    except Exception:
                        continue
        return None
    
    def chunk_chapter(
        self,
        book_id: str,
        chapter_title: str,
        chunk_duration_minutes: float = 1.0,
        target_chars: Optional[int] = None,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chunk a chapter's text into segments.
        
        This creates chunk metadata but does NOT generate audio files.
        The chunks are stored in metadata for later TTS processing.
        
        Args:
            book_id: Book identifier
            chapter_title: Chapter title (filename without extension)
            chunk_duration_minutes: Target duration per chunk in minutes
            target_chars: Optional target characters per chunk (overrides duration-based calculation)
            min_chars: Optional minimum characters per chunk
            max_chars: Optional maximum characters per chunk (defaults to 250 for XTTS v2)
            
        Returns:
            Dictionary with chunking results
        """
        logger.info(f"Chunking chapter: {book_id}/{chapter_title}")
        
        # Find book directory
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        chapters_dir = book_dir / "chapters"
        text_file = chapters_dir / f"{chapter_title}.txt"
        
        if not text_file.exists():
            raise FileNotFoundError(f"Chapter text file not found: {text_file}")
        
        # Read text
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
        
        # Build chunk metadata
        import time
        chunk_metadata = []
        for i, chunk_info in enumerate(chunk_data, 1):
            if isinstance(chunk_info, tuple):
                chunk_text, start_pos, end_pos = chunk_info
            else:
                chunk_text = chunk_info
                start_pos = text_content.find(chunk_text)
                end_pos = start_pos + len(chunk_text) if start_pos >= 0 else len(chunk_text)
            
            chunk_metadata.append({
                'index': i,
                'text_start': start_pos,
                'text_end': end_pos,
                'text_length': len(chunk_text),
                'status': 'pending',  # Chunks start as pending until TTS is generated
                'created_at': time.time(),
            })
        
        # Adjust chunk end positions to eliminate gaps
        for i in range(len(chunk_metadata) - 1):
            current_chunk = chunk_metadata[i]
            next_chunk = chunk_metadata[i + 1]
            current_end = current_chunk.get('text_end', 0)
            next_start = next_chunk.get('text_start', 0)
            
            if current_end < next_start:
                current_chunk['text_end'] = next_start
                current_chunk['text_length'] = next_start - current_chunk.get('text_start', 0)
        
        # Update metadata tracker
        tracker = MetadataTracker(book_dir)
        tracker.update_chunk_metadata(chapter_title, chunk_metadata)
        tracker.update_chunk_count(chapter_title, len(chunk_metadata))
        
        logger.info(f"✅ Created {len(chunk_metadata)} chunks for chapter: {chapter_title}")
        
        return {
            'chapter_title': chapter_title,
            'chunk_count': len(chunk_metadata),
            'chunks': chunk_metadata,
            'total_text_length': len(text_content),
        }
    
    def get_chunk_text(self, book_id: str, chapter_title: str, chunk_index: int) -> Optional[str]:
        """
        Get the text content for a specific chunk.
        
        Args:
            book_id: Book identifier
            chapter_title: Chapter title
            chunk_index: Chunk index (1-based)
            
        Returns:
            Chunk text content or None if not found
        """
        book_dir = self.find_book_dir(book_id)
        if not book_dir:
            return None
        
        chapters_dir = book_dir / "chapters"
        text_file = chapters_dir / f"{chapter_title}.txt"
        
        if not text_file.exists():
            return None
        
        # Get chunk metadata
        tracker = MetadataTracker(book_dir)
        metadata = tracker.load()
        chapter_meta = next(
            (ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title),
            None
        )
        
        if not chapter_meta:
            return None
        
        chunk_metadata_list = chapter_meta.get('chunk_metadata', [])
        chunk_meta = next(
            (ch for ch in chunk_metadata_list if ch.get('index') == chunk_index),
            None
        )
        
        if not chunk_meta:
            return None
        
        # Read text file and extract chunk
        text_content = text_file.read_text(encoding='utf-8')
        start_pos = chunk_meta.get('text_start', 0)
        end_pos = chunk_meta.get('text_end', len(text_content))
        
        return text_content[start_pos:end_pos]

