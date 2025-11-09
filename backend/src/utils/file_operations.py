"""File operations for reading/writing text and audio files.

This module handles filesystem operations separately from data access.
Metadata is stored in the database, but actual files (text, audio) remain on filesystem.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from src.models.book import Book
from src.models.chapter import Chapter
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus

logger = logging.getLogger(__name__)


def read_text_file(file_path: Path) -> Optional[str]:
    """Read text content from a file.
    
    Args:
        file_path: Path to text file
        
    Returns:
        Text content or None if file doesn't exist or read fails
    """
    if not file_path.exists():
        return None
    try:
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read text file {file_path}: {e}")
        return None


def write_text_file(file_path: Path, content: str) -> bool:
    """Write text content to a file.
    
    Args:
        file_path: Path to text file
        content: Text content to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        logger.error(f"Failed to write text file {file_path}: {e}")
        return False


def save_book_metadata(book: Book) -> bool:
    """Save book metadata JSON file to filesystem.
    
    Note: Book metadata is also saved to database via repository.
    This function handles the filesystem metadata.json file for backward compatibility.
    
    Args:
        book: Book instance
        
    Returns:
        True if successful, False otherwise
    """
    if book.path is None:
        logger.error("Cannot save book metadata: book.path is None")
        return False
    
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
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved book metadata to {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save book metadata to {metadata_path}: {e}")
        return False


def save_chapter_metadata(chapter: Chapter) -> bool:
    """Save chapter metadata JSON file to filesystem.
    
    Note: Chapter metadata is also saved to database via repository.
    This function handles the filesystem metadata.json file for backward compatibility.
    
    Args:
        chapter: Chapter instance
        
    Returns:
        True if successful, False otherwise
    """
    if chapter.path is None:
        logger.error("Cannot save chapter metadata: chapter.path is None")
        return False
    
    chapter_dir = Path(chapter.path)
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = chapter_dir / "metadata.json"
    metadata = {
        'id': chapter.id,
        'book_id': chapter.book_id,
        'chapter_number': chapter.chapter_number,
        'number': chapter.number,
        'title': chapter.title,
        'url': chapter.url,
        'word_count': chapter.text_size,
    }
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved chapter metadata to {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save chapter metadata to {metadata_path}: {e}")
        return False


def save_chunk_metadata(chunk: Chunk) -> bool:
    """Save chunk metadata JSON file to filesystem.
    
    Note: Chunk metadata is also saved to database via repository.
    This function handles the filesystem metadata.json file for backward compatibility.
    
    Args:
        chunk: Chunk instance
        
    Returns:
        True if successful, False otherwise
    """
    if chunk.path is None:
        logger.error("Cannot save chunk metadata: chunk.path is None")
        return False
    
    chunk_dir = Path(chunk.path)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_path = chunk_dir / "metadata.json"
    metadata = {
        'index': chunk.index,
        'book_id': chunk.book_id,
        'chapter_id': chunk.chapter_id,
        'text_start': chunk.text_start,
        'text_end': chunk.text_end,
        'status': chunk.status.value,
        'generation_time_seconds': chunk.generation_time_seconds,
        'audio_duration_seconds': chunk.audio_duration_seconds,
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
            f.flush()
            import os
            os.fsync(f.fileno())  # Force write to disk
        logger.debug(f"Saved chunk metadata to {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save chunk metadata to {metadata_path}: {e}")
        return False


def get_chunk_text(chunk: Chunk) -> Optional[str]:
    """Get text content for a chunk by reading from filesystem.
    
    Args:
        chunk: Chunk instance (must have path set)
        
    Returns:
        Text content or None if not found
    """
    if chunk.text_path is None:
        return None
    return read_text_file(chunk.text_path)


def get_chapter_text(chapter: Chapter) -> Optional[str]:
    """Get text content for a chapter by reading from filesystem.
    
    Args:
        chapter: Chapter instance (must have path set)
        
    Returns:
        Text content or None if not found
    """
    if chapter.text_path is None:
        return None
    return read_text_file(chapter.text_path)


def get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get audio duration in seconds from WAV file.
    
    Args:
        audio_path: Path to WAV file
        
    Returns:
        Duration in seconds or None if unable to read
    """
    if not audio_path.exists():
        return None
    try:
        import wave
        with wave.open(str(audio_path), 'rb') as wav_file:
            n_frames = wav_file.getnframes()
            framerate = wav_file.getframerate()
            return n_frames / framerate if framerate > 0 else None
    except Exception as e:
        logger.debug(f"Failed to read audio duration from {audio_path}: {e}")
        return None

