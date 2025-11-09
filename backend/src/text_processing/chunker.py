"""Text chunking with metadata for TTS synthesis."""

import logging
import re
from typing import List, Optional, Tuple

from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.text_processing.chunk_metadata import ChunkMetadata
from src.text_processing.config import TextProcessingConfig
from src.text_processing.segmenter import TextSegmenter

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Chunks text with metadata for TTS synthesis.
    
    Simple sequential splitting that preserves ALL characters.
    Splits on natural boundaries (paragraphs → sentences → commas → whitespace).
    Guarantees: concatenating all chunks returns the exact original text.
    """
    
    # Split character sets to search for (in priority order)
    # Each tuple: (description, check_function)
    SPLIT_STRATEGIES = [
        # Pass 1: Paragraph breaks (double newline)
        ("paragraph breaks", lambda chunk, i: (
            i > 0 and 
            chunk[i - 1] == '\n' and 
            chunk[i] == '\n'
        )),
        # Pass 2: Sentence endings (punctuation + space)
        ("sentence endings", lambda chunk, i: (
            i > 0 and 
            chunk[i - 1] in '.!?' and 
            chunk[i] in ' \n\t'
        )),
        # Pass 3: Commas and semicolons (with trailing whitespace)
        ("commas/semicolons", lambda chunk, i: (
            i > 0 and
            chunk[i - 1] in ',;:' and
            i < len(chunk) and
            chunk[i] in ' \n\t'
        )),
        # Pass 4: Any whitespace
        ("whitespace", lambda chunk, i: chunk[i] in ' \n\t'),
    ]
    
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        """
        Initialize text chunker.
        
        Args:
            config: Optional TextProcessingConfig instance
        """
        self.config = config or TextProcessingConfig()
        self.segmenter = TextSegmenter(self.config)
    
    def chunk_by_paragraphs(
        self,
        text: str,
        target_chars_per_minute: int = 200,  # Legacy parameter, kept for compatibility
        min_chars: int = 50,
        max_chars: int = 250,  # XTTS v2 limit
        default_voice_name: Optional[str] = None,
        default_speed: Optional[float] = None,
        book_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
    ) -> List[Chunk]:
        """
        Chunk text with character limits using Chunkipy.
        
        Simple 3-step process:
        1. Use Chunkipy to intelligently split text
        2. Map chunks back to original text positions
        3. Create Chunk objects with metadata
        
        Args:
            text: Full text to chunk
            target_chars_per_minute: Legacy parameter (ignored)
            min_chars: Minimum characters per chunk (advisory)
            max_chars: Maximum characters per chunk (hard limit for XTTS v2)
            default_voice_name: Default voice name to apply to all chunks
            default_speed: Default speed to apply to all chunks
            book_id: Optional book ID for chunks
            chapter_id: Optional chapter ID for chunks
            
        Returns:
            List of Chunk objects with contiguous coverage
        """
        # Handle empty text
        if not text or not text.strip():
            return []
        
        # XTTS v2 has a hard 250 char limit
        XTTS_V2_CHAR_LIMIT = 250
        effective_max_chars = min(max_chars, XTTS_V2_CHAR_LIMIT)
        
        # Step 1: Split text into chunks using intelligent fallback
        # This ensures we process the text sequentially with NO gaps
        text_chunks = self._fallback_split(text, effective_max_chars)
        
        # Step 2: Map chunks sequentially to positions (guaranteed contiguous)
        chunks = []
        pos = 0
        
        for i, chunk_text in enumerate(text_chunks, 1):
            chunk_start = pos
            chunk_end = pos + len(chunk_text)
            
            # Create Chunk object with metadata
            chunk = self._create_chunk(
                chunk_text=chunk_text,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                index=i,
                book_id=book_id,
                chapter_id=chapter_id,
                default_voice_name=default_voice_name,
                default_speed=default_speed,
        )
        
            chunks.append(chunk)
            pos = chunk_end
        
        return chunks
    
    def _fallback_split(self, text: str, max_chars: int) -> List[str]:
        """
        Dead simple sequential text splitting that preserves ALL characters.
        
        Algorithm:
        1. Take up to max_chars characters
        2. Search backwards for safe split point (paragraph → sentence → comma → space)
        3. If no safe point found, raise error (no hard truncation)
        
        Guarantees: ''.join(result) == text (no gaps, no modifications)
        """
        if not text:
            return []
        
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        pos = 0
        
        while pos < len(text):
            # Take up to max_chars
            remaining = text[pos:]
            if len(remaining) <= max_chars:
                # Last chunk - take everything
                chunks.append(remaining)
                break
            
            chunk = remaining[:max_chars]
            split_at = None
            
            # Try each split strategy in order (sentence → comma → whitespace)
            for strategy_name, check_fn in self.SPLIT_STRATEGIES:
                for i in range(len(chunk) - 1, 0, -1):
                    if check_fn(chunk, i):
                        # For sentence endings, include the space after punctuation
                        # For commas/whitespace, include the character itself
                        split_at = i + 1
                        break
                
                if split_at is not None:
                    break  # Found a split point, stop searching
            
            # If still no split point found, this is an error condition
            # No whitespace in max_chars characters indicates bad input data
            if split_at is None:
                logger.error(
                    f"Cannot split text at position {pos}: no whitespace found in {max_chars} characters. "
                    f"Text preview: {chunk[:100]}..."
                )
                raise ValueError(
                    f"Cannot safely split text: no whitespace found in {max_chars} characters. "
                    "This indicates a data quality issue or malformed input."
                )
            
            chunks.append(text[pos:pos + split_at])
            pos += split_at
        
        return chunks
    
    def _create_chunk(
        self,
        chunk_text: str,
        chunk_start: int,
        chunk_end: int,
        index: int,
        book_id: Optional[str],
        chapter_id: Optional[str],
        default_voice_name: Optional[str],
        default_speed: Optional[float],
    ) -> Chunk:
        """
        Create a Chunk object from text and positions.
        
        Analyzes text for metadata (dialogue, scene breaks, etc.).
        
        Note: Assumes chunk_text is already properly sized (≤250 chars).
        Hard truncation is NOT safe as it can split mid-word/character.
        """
        # Validation: This should never happen if chunking logic is correct
        if len(chunk_text) > 250:
            # Log error but don't truncate - let it fail visibly
            logger.error(
                f"Chunk {index} exceeds 250 chars ({len(chunk_text)} chars). "
                f"This indicates a bug in chunking logic. Text: {chunk_text[:100]}..."
            )
            # Raise exception rather than silently corrupting text
            raise ValueError(
                f"Chunk size {len(chunk_text)} exceeds XTTS v2 limit of 250 characters. "
                "This is a bug in the chunking logic that must be fixed."
            )
        
        # Analyze metadata
        metadata = self._analyze_chunk_metadata(
            chunk_text, default_voice_name, default_speed
        )
        
        return Chunk(
            index=index,
            book_id=book_id or '',
            text_start=chunk_start,
            text_end=chunk_end,
            status=ChunkStatus.PENDING,
            chapter_id=chapter_id,
            path=None,
            generation_time_seconds=None,
            voice_name=metadata.voice_name,
            speed=metadata.speed,
            pre_pause_ms=metadata.pre_pause_ms,
            post_pause_ms=metadata.post_pause_ms,
            is_dialogue=metadata.is_dialogue,
            is_scene_break=metadata.is_scene_break,
        )
    
    def _analyze_chunk_metadata(
        self,
        text: str,
        default_voice_name: Optional[str] = None,
        default_speed: Optional[float] = None,
    ) -> ChunkMetadata:
        """
        Analyze chunk text to determine metadata.
        
        Detects:
        - Dialogue (quotes)
        - Scene breaks (*** or multiple paragraph breaks)
        - Speaker hints (for voice selection)
        
        Args:
            text: Chunk text
            default_voice_name: Default voice name
            default_speed: Default speed
            
        Returns:
            ChunkMetadata object with analyzed metadata
        """
        # Detect dialogue (for metadata only, not for voice assignment)
        is_dialogue = self.segmenter.detect_dialogue(text)
        
        # Detect scene breaks
        is_scene_break = '***' in text or text.count('\n\n') >= 2
        
        # Always use narrator voice (default_voice_name)
        # Speaker extraction removed - voice assignment needs to be paired with
        # proper dialogue chunking (separating quotes from "said" parts)
        voice_name = default_voice_name
        
        # Set scene break pause
        pre_pause_ms = 900 if is_scene_break else 0
        
        return ChunkMetadata(
            voice_name=voice_name,
            speed=default_speed,
            pre_pause_ms=pre_pause_ms,
            post_pause_ms=0,
            is_dialogue=is_dialogue,
            is_scene_break=is_scene_break,
                )
