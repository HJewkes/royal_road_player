"""Text chunking utilities for long-form TTS generation."""

import re
from typing import List, Tuple, Optional
from pathlib import Path

from src.tts.segmenter import segment_all, Segment
from src.tts.segmentation_config import get_default_config, load_config_from_file


def chunk_text_by_paragraphs(
    text: str,
    target_chars_per_minute: int = 9000,
    min_chars: int = 3000,
    max_chars: int = 15000,
    max_tokens: int = 400,  # XTTS v2 hard limit
    return_positions: bool = False,
) -> List[str] | List[tuple[str, int, int]]:
    """
    Chunk text at paragraph boundaries targeting ~1 minute of audio per chunk.
    
    This function splits text into paragraphs, then groups them until reaching
    the target size. Always breaks at paragraph boundaries (never mid-paragraph).
    
    IMPORTANT: XTTS v2 has a hard limit of 400 tokens per generation.
    Rough estimate: 1 token ≈ 4 characters, so max_chars should be ~1500-2000.
    
    Args:
        text: Full text to chunk
        target_chars_per_minute: Target characters per minute of audio (~9000 for XTTS v2)
        min_chars: Minimum characters per chunk (to avoid tiny chunks)
        max_chars: Maximum characters per chunk (hard limit, must respect token limit)
        max_tokens: Maximum tokens per chunk (XTTS v2 limit: 400)
        return_positions: If True, return tuples of (chunk_text, start_pos, end_pos)
        
    Returns:
        List of chunk text strings (each targeting ~1 minute of audio)
        OR List of tuples (chunk_text, start_pos, end_pos) if return_positions=True
    """
    # CRITICAL: XTTS v2 has a 250 character limit per synthesis call
    # This is stricter than the token limit, so we must enforce it
    XTTS_V2_CHAR_LIMIT = 250
    
    # Use the stricter limit (250 char limit or provided max_chars)
    effective_max_chars = min(max_chars, XTTS_V2_CHAR_LIMIT)
    
    # Also adjust target to be within the limit
    if target_chars_per_minute > effective_max_chars:
        target_chars_per_minute = effective_max_chars
    # Split text into paragraphs preserving EXACT original formatting
    # No normalization, no processing - just split by paragraph breaks
    # Paragraph break = empty line (one or more consecutive newlines)
    paragraphs = []
    
    # Split by empty lines (one or more newlines) while preserving exact text
    # Include empty lines in paragraph end positions so chunks are continuous
    lines = text.split('\n')
    para_lines = []
    para_start = 0
    line_pos = 0
    
    for i, line in enumerate(lines):
        line_end = line_pos + len(line)
        
        if line.strip():  # Non-empty line - part of current paragraph
            if not para_lines:
                para_start = line_pos
            para_lines.append(line)
        else:  # Empty line - paragraph break
            if para_lines:
                # End of paragraph - include the empty line in end position
                para_text = '\n'.join(para_lines)
                # End position includes the empty line and its newline
                # This makes chunks continuous (no gaps)
                para_end = line_end + 1  # +1 for the newline after empty line
                paragraphs.append((para_text, para_start, para_end))
                para_lines = []
        
        # Move to next line (add 1 for newline character)
        line_pos = line_end + 1
    
    # Add final paragraph if exists
    if para_lines:
        para_text = '\n'.join(para_lines)
        para_end = len(text)
        paragraphs.append((para_text, para_start, para_end))
    
    # If no paragraphs found, treat entire text as one paragraph
    if not paragraphs:
        paragraphs.append((text, 0, len(text)))
    
    # Group paragraphs into chunks targeting ~1 minute each
    chunks = []
    current_chunk = []
    current_size = 0
    chunk_start_pos = 0  # Track start position of current chunk in original text
    
    for para_info in paragraphs:
        if isinstance(para_info, tuple):
            para, para_start, para_end = para_info
        else:
            para = para_info
            # Fallback: try to find paragraph in text
            para_start = text.find(para)
            para_end = para_start + len(para) if para_start >= 0 else len(para)
        # Use actual position difference, not text length (includes empty lines)
        para_size = para_end - para_start
        
        # CRITICAL: If a single paragraph exceeds the limit, split it at sentence boundaries
        if para_size > effective_max_chars:
            # Split paragraph into sentences and group them
            import re
            sentences = re.split(r'([.!?]+\s+)', para)
            # Recombine sentences with their punctuation
            sentence_parts = []
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    sentence_parts.append(sentences[i] + sentences[i + 1])
                else:
                    sentence_parts.append(sentences[i])
            if len(sentences) % 2 == 1:
                sentence_parts.append(sentences[-1])
            
            # Process each sentence or group of sentences
            for sentence in sentence_parts:
                sentence = sentence.strip()
                if not sentence:
                    continue
                sent_size = len(sentence)
                
                # If sentence itself exceeds limit, we must truncate (shouldn't happen often)
                if sent_size > effective_max_chars:
                    # Split at word boundaries as last resort
                    words = sentence.split()
                    current_sent = []
                    current_sent_size = 0
                    for word in words:
                        word_with_space = word + ' '
                        if current_sent_size + len(word_with_space) > effective_max_chars and current_sent:
                            # Add current sentence as a paragraph
                            para_to_add = ' '.join(current_sent)
                            para_size = len(para_to_add)
                            # Process this as a normal paragraph
                            if current_size + para_size > effective_max_chars and current_chunk:
                                # Save current chunk and start new one
                                chunk_text = '\n\n'.join(current_chunk)
                                if len(chunk_text.strip()) >= min_chars:
                                    if return_positions:
                                        chunk_start = text.find(chunk_text, text_pos - len(chunk_text) - 100)
                                        if chunk_start == -1:
                                            chunk_start = text.find(chunk_text)
                                        if chunk_start == -1:
                                            chunk_start = text_pos
                                        chunk_end = chunk_start + len(chunk_text)
                                        chunks.append((chunk_text, chunk_start, chunk_end))
                                        text_pos = chunk_end
                                    else:
                                        chunks.append(chunk_text)
                                current_chunk = [para_to_add]
                                current_size = para_size
                            elif current_size + para_size <= target_chars_per_minute:
                                current_chunk.append(para_to_add)
                                current_size += para_size + 2
                            elif current_size < min_chars:
                                current_chunk.append(para_to_add)
                                current_size += para_size + 2
                            else:
                                chunk_text = '\n\n'.join(current_chunk)
                                if return_positions:
                                    chunk_start = text.find(chunk_text, max(0, text_pos - len(chunk_text) - 100))
                                    if chunk_start == -1:
                                        chunk_start = text.find(chunk_text)
                                    if chunk_start == -1:
                                        chunk_start = text_pos
                                    chunk_end = chunk_start + len(chunk_text)
                                    chunks.append((chunk_text, chunk_start, chunk_end))
                                    text_pos = chunk_end
                                else:
                                    chunks.append(chunk_text)
                                current_chunk = [para_to_add]
                                current_size = para_size
                            current_sent = [word]
                            current_sent_size = len(word_with_space)
                        else:
                            current_sent.append(word)
                            current_sent_size += len(word_with_space)
                    # Add remaining sentence
                    if current_sent:
                        para_to_add = ' '.join(current_sent)
                        para_size = len(para_to_add)
                        # Process this as a normal paragraph (same logic as above)
                        if current_size + para_size > effective_max_chars and current_chunk:
                            chunk_text = '\n\n'.join(current_chunk)
                            if len(chunk_text.strip()) >= min_chars:
                                if return_positions:
                                    chunk_start = text.find(chunk_text, text_pos - len(chunk_text) - 100)
                                    if chunk_start == -1:
                                        chunk_start = text.find(chunk_text)
                                    if chunk_start == -1:
                                        chunk_start = text_pos
                                    chunk_end = chunk_start + len(chunk_text)
                                    chunks.append((chunk_text, chunk_start, chunk_end))
                                    text_pos = chunk_end
                                else:
                                    chunks.append(chunk_text)
                            current_chunk = [para_to_add]
                            current_size = para_size
                        elif current_size + para_size <= target_chars_per_minute:
                            current_chunk.append(para_to_add)
                            current_size += para_size + 2
                        elif current_size < min_chars:
                            current_chunk.append(para_to_add)
                            current_size += para_size + 2
                        else:
                            chunk_text = '\n\n'.join(current_chunk)
                            if return_positions:
                                chunk_start = text.find(chunk_text, max(0, text_pos - len(chunk_text) - 100))
                                if chunk_start == -1:
                                    chunk_start = text.find(chunk_text)
                                if chunk_start == -1:
                                    chunk_start = text_pos
                                chunk_end = chunk_start + len(chunk_text)
                                chunks.append((chunk_text, chunk_start, chunk_end))
                                text_pos = chunk_end
                            else:
                                chunks.append(chunk_text)
                            current_chunk = [para_to_add]
                            current_size = para_size
                    continue
        
        # Calculate what the chunk size would be if we add this paragraph
        # This includes all whitespace between paragraphs
        if current_chunk:
            # Size would be from first paragraph start to this paragraph end
            # This naturally includes all whitespace/empty lines between paragraphs
            would_be_size = para_end - current_chunk[0][1]
        else:
            would_be_size = para_size
        
        # Strategy: Combine paragraphs until we hit the max limit
        # Always break ONLY at paragraph boundaries (never mid-paragraph)
        # Combine multiple short paragraphs together, preserving whitespace between them
        
        # If adding this paragraph would exceed max AND we have a chunk, save it and start new
        if would_be_size > effective_max_chars and current_chunk:
            # Save current chunk - extract text from original using tracked positions
            chunk_start = current_chunk[0][1]
            chunk_end = current_chunk[-1][2]
            chunk_text = text[chunk_start:chunk_end]  # Extract exact text preserving formatting
            # Always save chunks, even if small (to preserve all text including headers)
            if return_positions:
                chunks.append((chunk_text, chunk_start, chunk_end))
                chunk_start_pos = chunk_end
            else:
                chunks.append(chunk_text)
            # Start new chunk with this paragraph
            current_chunk = [(para, para_start, para_end)]
            current_size = para_size
        # If adding this paragraph keeps us within target, combine it
        elif would_be_size <= target_chars_per_minute:
            current_chunk.append((para, para_start, para_end))
            # Size is from first paragraph start to last paragraph end (includes whitespace)
            current_size = para_end - current_chunk[0][1]
        # If adding would exceed target but current chunk is too small, add anyway
        # (This prevents tiny chunks and combines short paragraphs)
        elif current_size < min_chars:
            current_chunk.append((para, para_start, para_end))
            current_size = para_end - current_chunk[0][1]
        # If the paragraph itself is short, combine it even if we're at target
        # This ensures short paragraphs get combined together
        elif para_size < min_chars:
            current_chunk.append((para, para_start, para_end))
            current_size = para_end - current_chunk[0][1]
        # Otherwise, we've hit target and paragraph is substantial - start new chunk
        else:
            # Save current chunk
            chunk_start = current_chunk[0][1]
            chunk_end = current_chunk[-1][2]
            chunk_text = text[chunk_start:chunk_end]  # Extract exact text preserving formatting
            # Always save chunks, even if small (to preserve all text including headers)
            if return_positions:
                chunks.append((chunk_text, chunk_start, chunk_end))
                chunk_start_pos = chunk_end
            else:
                chunks.append(chunk_text)
            # Start new chunk with this paragraph
            current_chunk = [(para, para_start, para_end)]
            current_size = para_size
    
    # Add final chunk
    if current_chunk:
        chunk_start = current_chunk[0][1]
        chunk_end = current_chunk[-1][2]
        chunk_text = text[chunk_start:chunk_end]  # Extract exact text preserving formatting
        if chunk_text.strip():
            if return_positions:
                chunks.append((chunk_text, chunk_start, chunk_end))
            else:
                chunks.append(chunk_text)
    
    return chunks


def chunk_text(
    text: str,
    max_chunk_size: int = 5000,
    overlap: int = 100,
    prefer_sentence_boundaries: bool = True,
) -> List[Tuple[str, int, int]]:
    """
    Chunk text into smaller pieces for TTS generation.

    Args:
        text: Full text to chunk
        max_chunk_size: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks (for smooth transitions)
        prefer_sentence_boundaries: Try to break at sentence boundaries when possible

    Returns:
        List of tuples: (chunk_text, start_index, end_index)
    """
    chunks = []
    text_length = len(text)
    current_pos = 0

    while current_pos < text_length:
        # Determine chunk end position
        chunk_end = min(current_pos + max_chunk_size, text_length)

        # If we prefer sentence boundaries and we're not at the end
        if prefer_sentence_boundaries and chunk_end < text_length:
            # Look for sentence endings near the chunk boundary
            # Check last 200 characters for sentence endings
            search_start = max(current_pos, chunk_end - 200)
            search_text = text[search_start:chunk_end + 50]

            # Find sentence boundaries (period, exclamation, question mark followed by space)
            sentence_endings = list(re.finditer(r'[.!?]\s+', search_text))
            if sentence_endings:
                # Use the last sentence ending before the max size
                last_ending = sentence_endings[-1]
                chunk_end = search_start + last_ending.end()

        # Extract chunk
        chunk_text_segment = text[current_pos:chunk_end].strip()

        if chunk_text_segment:
            chunks.append((chunk_text_segment, current_pos, chunk_end))

        # Move to next chunk (with overlap)
        if chunk_end >= text_length:
            break
        current_pos = max(current_pos + 1, chunk_end - overlap)

    return chunks


def chunk_segments_by_paragraphs(
    segments: List[Segment],
    target_chars_per_minute: int = 9000,
    min_chars: int = 3000,
    max_chars: int = 15000,
    max_tokens: int = 400,  # XTTS v2 hard limit
) -> List[List[Segment]]:
    """
    Chunk segments into groups targeting ~1 minute of audio per chunk.
    
    This function groups segments until reaching target size, respecting
    the XTTS v2 token limit. Always breaks at segment boundaries.
    
    Args:
        segments: List of Segment objects
        target_chars_per_minute: Target characters per minute of audio
        min_chars: Minimum characters per chunk
        max_chars: Maximum characters per chunk
        max_tokens: Maximum tokens per chunk (XTTS v2 limit: 400)
        
    Returns:
        List of chunk lists (each containing Segment objects)
    """
    # Estimate tokens from characters (rough: 1 token ≈ 4 characters)
    # But be conservative: use 3.5 chars/token to account for punctuation
    estimated_max_chars = int(max_tokens * 3.5)
    
    # Use the stricter limit (token-based or provided max_chars)
    effective_max_chars = min(max_chars, estimated_max_chars)
    
    # Also adjust target to be within token limit
    if target_chars_per_minute > effective_max_chars:
        target_chars_per_minute = effective_max_chars
    
    # Group segments into chunks
    chunks = []
    current_chunk = []
    current_size = 0
    
    for segment in segments:
        segment_size = len(segment.text)
        
        # If adding this segment would exceed max, start new chunk
        if current_size + segment_size > effective_max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [segment]
            current_size = segment_size
        # If current chunk is below target, add segment
        elif current_size + segment_size <= target_chars_per_minute:
            current_chunk.append(segment)
            current_size += segment_size
        # If adding would exceed target but current chunk is too small, add anyway
        elif current_size < min_chars:
            current_chunk.append(segment)
            current_size += segment_size
        # Otherwise, start new chunk
        else:
            chunks.append(current_chunk)
            current_chunk = [segment]
            current_size = segment_size
    
    # Add final chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def chunk_text_with_segmentation(
    paragraphs: List[str],
    target_chars_per_minute: int = 9000,
    min_chars: int = 3000,
    max_chars: int = 15000,
    max_tokens: int = 400,
    segmentation_config: Optional[dict] = None,
) -> List[str]:
    """
    Chunk text using breath-group segmentation.
    
    This is the new recommended chunking function that first segments
    text into breath-groups, then groups segments into chunks.
    
    Args:
        paragraphs: List of paragraph strings
        target_chars_per_minute: Target characters per minute
        min_chars: Minimum characters per chunk
        max_chars: Maximum characters per chunk
        max_tokens: Maximum tokens per chunk
        segmentation_config: Optional segmentation config dict
        
    Returns:
        List of chunk text strings
    """
    if segmentation_config is None:
        segmentation_config = get_default_config()
    
    # First, segment paragraphs into breath-groups
    segments = segment_all(paragraphs, segmentation_config)
    
    # Then, chunk segments into groups
    segment_chunks = chunk_segments_by_paragraphs(
        segments,
        target_chars_per_minute=target_chars_per_minute,
        min_chars=min_chars,
        max_chars=max_chars,
        max_tokens=max_tokens,
    )
    
    # Convert segment chunks back to text strings
    text_chunks = []
    for segment_chunk in segment_chunks:
        chunk_text = ' '.join(seg.text for seg in segment_chunk)
        text_chunks.append(chunk_text)
    
    return text_chunks


def estimate_generation_time(text_length: int, chars_per_second: float = 100) -> float:
    """
    Estimate TTS generation time.

    Args:
        text_length: Number of characters
        chars_per_second: Estimated characters per second (default: 100 for CPU, 200-500 for GPU)

    Returns:
        Estimated time in seconds
    """
    return text_length / chars_per_second


def should_chunk(text: str, max_chunk_size: int = 10000) -> bool:
    """
    Determine if text should be chunked.

    Args:
        text: Text to check
        max_chunk_size: Maximum recommended chunk size

    Returns:
        True if text should be chunked
    """
    return len(text) > max_chunk_size

