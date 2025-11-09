"""Text chunking with metadata for TTS synthesis."""

import re
from typing import List, Optional

import attr

from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.text_processing.config import TextProcessingConfig
from src.text_processing.segmenter import TextSegmenter


@attr.s(auto_attribs=True)
class TextSegment:
    """A text segment with position information."""
    text: str
    start_pos: int
    end_pos: int
    
    @property
    def size(self) -> int:
        """Get segment size in characters."""
        return len(self.text)


class TextChunker:
    """Chunks text with metadata for TTS synthesis."""
    
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
        target_chars_per_minute: int = 200,  # Target chars per chunk (not per minute)
        min_chars: int = 50,
        max_chars: int = 250,  # XTTS v2 limit
        default_voice_name: Optional[str] = None,
        default_speed: Optional[float] = None,
        book_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
    ) -> List[Chunk]:
        """
        Chunk text at paragraph boundaries with metadata.
        
        Args:
            text: Full text to chunk
            target_chars_per_minute: Target characters per chunk (misnamed, kept for compatibility)
            min_chars: Minimum characters per chunk
            max_chars: Maximum characters per chunk (must respect XTTS v2 250 char limit)
            default_voice_name: Default voice name to apply to all chunks
            default_speed: Default speed to apply to all chunks
            book_id: Optional book ID for chunks
            chapter_id: Optional chapter ID for chunks
            
        Returns:
            List of Chunk objects
        """
        XTTS_V2_CHAR_LIMIT = 250
        effective_max_chars = min(max_chars, XTTS_V2_CHAR_LIMIT)
        
        # Step 1: Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        # Step 2: Process paragraphs - split oversized ones
        processed_segments: List[TextSegment] = []
        for para_text, para_start, para_end in paragraphs:
            para_size = para_end - para_start
            
            if para_size > effective_max_chars:
                # Paragraph too long - split it
                segments = self._split_oversized_paragraph(para_text, para_start, para_end, effective_max_chars)
                processed_segments.extend(segments)
            else:
                # Paragraph fits - use as-is
                processed_segments.append(TextSegment(para_text, para_start, para_end))
        
        # Step 3: Merge segments into chunks (ensures contiguous coverage)
        chunks = self._merge_segments_into_chunks(
            processed_segments,
            text,
            effective_max_chars,
            book_id,
            chapter_id,
            default_voice_name,
            default_speed,
        )
        
        # Step 4: Detect scene breaks and adjust pauses
        self._detect_scene_breaks(chunks)
        
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[tuple[str, int, int]]:
        """
        Split text into paragraphs with positions.
        
        Important: Split characters (newlines, etc.) are kept at the END of the first chunk.
        No characters are ever removed - they're always included in one chunk or another.
        """
        paragraphs = []
        lines = text.split('\n')
        para_lines = []
        para_start = 0
        line_pos = 0
        
        for i, line in enumerate(lines):
            line_end = line_pos + len(line)
            is_last_line = (i == len(lines) - 1)
            
            if line.strip():
                # Non-empty line - start or continue paragraph
                if not para_lines:
                    para_start = line_pos
                para_lines.append(line)
            else:
                # Empty line (whitespace) - this is a split point
                if para_lines:
                    # We have a paragraph - include this empty line and its newline
                    # at the END of the current paragraph (split characters stay with first chunk)
                    para_lines.append(line)  # Include empty line
                    para_text = '\n'.join(para_lines)
                    # para_end includes the newline after this empty line
                    para_end = line_end + 1 if not is_last_line else len(text)
                    paragraphs.append((para_text, para_start, para_end))
                    para_lines = []
                # If no para_lines, this is leading whitespace - will start a new paragraph
                # (but only if there's content after it)
        
        # Handle final paragraph (if any remaining lines)
        if para_lines:
            para_text = '\n'.join(para_lines)
            paragraphs.append((para_text, para_start, len(text)))
        
        # Handle case where text starts with whitespace or is all whitespace
        if not paragraphs:
            paragraphs.append((text, 0, len(text)))
        
        return paragraphs
    
    def _split_oversized_paragraph(
        self,
        para_text: str,
        para_start: int,
        para_end: int,
        max_chars: int,
    ) -> List[TextSegment]:
        """
        Split an oversized paragraph into smaller segments.
        
        Tries splitting methods in order:
        1. Sentence boundaries
        2. Punctuation marks (commas, semicolons, em-dashes)
        3. Word boundaries (last resort)
        """
        # Try sentence splitting first
        sentences = self._split_sentences(para_text)
        segments = []
        
        for sentence in sentences:
            sentence_start = para_text.find(sentence)
            if sentence_start == -1:
                sentence_start = 0
            
            abs_start = para_start + sentence_start
            abs_end = abs_start + len(sentence)
            
            if len(sentence) > max_chars:
                # Sentence still too long - try punctuation splitting
                punct_segments = self._split_by_punctuation(sentence, abs_start, max_chars)
                segments.extend(punct_segments)
            else:
                segments.append(TextSegment(sentence, abs_start, abs_end))
        
        return segments
    
    def _split_at_delimiters(
        self,
        text: str,
        base_pos: int,
        max_chars: int,
        delimiter_pattern: str,
        merge_small: bool = False,
        fallback_delimiter: Optional[str] = None,
    ) -> List[TextSegment]:
        """
        Generic split method that splits text at delimiters.
        
        Args:
            text: Text to split
            base_pos: Base position in full text
            max_chars: Maximum characters per segment
            delimiter_pattern: Regex pattern for delimiters (e.g., r'[,;:—]')
            merge_small: If True, merge small segments if they fit within max_chars
            fallback_delimiter: If no matches found, use this delimiter (e.g., r'\s+' for words)
            
        Returns:
            List of TextSegment objects
        """
        pattern = re.compile(delimiter_pattern)
        matches = list(pattern.finditer(text))
        
        if not matches:
            # No matches - use fallback or return single segment
            if fallback_delimiter:
                return self._split_at_delimiters(
                    text, base_pos, max_chars, fallback_delimiter, merge_small=False, fallback_delimiter=None
                )
            return [TextSegment(text, base_pos, base_pos + len(text))]
        
        segments = []
        segment_start = 0
        
        for match in matches:
            segment_end = match.end()  # Include delimiter in segment
            segment_text = text[segment_start:segment_end]
            
            if len(segment_text) > max_chars:
                # Segment too long - use fallback delimiter or word splitting
                if fallback_delimiter:
                    word_segments = self._split_at_delimiters(
                        segment_text, base_pos + segment_start, max_chars,
                        fallback_delimiter, merge_small=False, fallback_delimiter=None
                    )
                    segments.extend(word_segments)
                else:
                    # Last resort: split at words
                    word_segments = self._split_at_words(segment_text, base_pos + segment_start, max_chars)
                    segments.extend(word_segments)
                segment_start = segment_end
            else:
                if merge_small and segments:
                    # Try to merge with previous segment
                    prev = segments[-1]
                    merged_size = (prev.end_pos - prev.start_pos) + len(segment_text)
                    if merged_size <= max_chars:
                        # Merge with previous
                        new_end = base_pos + segment_end
                        merged_text = text[prev.start_pos - base_pos:segment_end]
                        segments[-1] = TextSegment(merged_text, prev.start_pos, new_end)
                        segment_start = segment_end
                        continue
                
                # New segment
                abs_start = base_pos + segment_start
                abs_end = base_pos + segment_end
                segments.append(TextSegment(segment_text, abs_start, abs_end))
                segment_start = segment_end
        
        # Add final segment (always include, even if just whitespace - never remove characters)
        if segment_start < len(text):
            final_text = text[segment_start:]
            abs_start = base_pos + segment_start
            abs_end = base_pos + len(text)
            segments.append(TextSegment(final_text, abs_start, abs_end))
        
        return segments if segments else [TextSegment(text, base_pos, base_pos + len(text))]
    
    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences, preserving punctuation and trailing whitespace.
        
        Split characters (punctuation + following whitespace) are kept at the END
        of each sentence to ensure no characters are lost.
        """
        # Split at sentence endings, including any trailing whitespace up to next sentence start
        # Pattern: sentence ending punctuation followed by optional whitespace
        pattern = re.compile(r'([.!?]+)(\s*)')
        parts = pattern.split(text)
        
        sentences = []
        i = 0
        while i < len(parts):
            if i + 2 < len(parts):
                # parts[i] = sentence text, parts[i+1] = punctuation, parts[i+2] = whitespace
                # Include punctuation and whitespace at end of sentence (split chars stay with first chunk)
                sentences.append(parts[i] + parts[i + 1] + parts[i + 2])
                i += 3
            elif i + 1 < len(parts):
                # Just punctuation, no whitespace
                sentences.append(parts[i] + parts[i + 1])
                i += 2
            else:
                # Final part (no punctuation)
                if parts[i].strip():  # Only add if has content
                    sentences.append(parts[i])
                i += 1
        
        return sentences if sentences else [text]
    
    def _split_by_punctuation(self, text: str, base_pos: int, max_chars: int) -> List[TextSegment]:
        """Split text at punctuation marks (commas, semicolons, em-dashes)."""
        return self._split_at_delimiters(
            text, base_pos, max_chars, r'[,;:—]', merge_small=True, fallback_delimiter=r'\s+'
        )
    
    def _split_by_words(self, text: str, base_pos: int, max_chars: int) -> List[TextSegment]:
        """Split text at word boundaries (last resort)."""
        return self._split_at_words(text, base_pos, max_chars)
    
    def _split_at_words(self, text: str, base_pos: int, max_chars: int) -> List[TextSegment]:
        """Split text at word boundaries (whitespace)."""
        words = text.split()
        segments = []
        current_words = []
        current_start = base_pos
        
        for word in words:
            potential = ' '.join(current_words + [word]) if current_words else word
            
            if len(potential) > max_chars and current_words:
                # Save current segment
                segment_text = ' '.join(current_words)
                segments.append(TextSegment(segment_text, current_start, current_start + len(segment_text)))
                current_words = [word]
                current_start = current_start + len(segment_text) + 1
            else:
                current_words.append(word)
        
        # Add final segment
        if current_words:
            segment_text = ' '.join(current_words)
            segments.append(TextSegment(segment_text, current_start, base_pos + len(text)))
        
        return segments if segments else [TextSegment(text, base_pos, base_pos + len(text))]
    
    def _merge_segments_into_chunks(
        self,
        segments: List[TextSegment],
        full_text: str,
        max_chars: int,
        book_id: Optional[str],
        chapter_id: Optional[str],
        default_voice_name: Optional[str],
        default_speed: Optional[float],
    ) -> List[Chunk]:
        """
        Merge segments into chunks using a simple greedy algorithm.
        
        Simple loop: try to merge current + next, if fits continue,
        otherwise save current and move on. Ensures contiguous coverage.
        """
        if not segments:
            return []
        
        # First, create chunks from segments (one chunk per segment initially)
        chunks: List[Chunk] = []
        for segment in segments:
            chunk_text = full_text[segment.start_pos:segment.end_pos]
            chunk = self._create_chunk(
                chunk_text,
                segment.start_pos,
                segment.end_pos,
                len(chunks) + 1,
                book_id,
                chapter_id,
                default_voice_name,
                default_speed,
            )
            chunks.append(chunk)
        
        # Now merge chunks greedily
        merged_chunks: List[Chunk] = []
        current_chunk = chunks[0]
        
        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            
            # Try to merge current with next
            if current_chunk.can_merge_with(next_chunk, max_chars):
                # Can merge - merge them
                current_chunk = current_chunk.merge_with(next_chunk, len(merged_chunks) + 1)
            else:
                # Can't merge - save current and start new
                merged_chunks.append(current_chunk)
                current_chunk = next_chunk
        
        # Add final chunk
        merged_chunks.append(current_chunk)
        
        # Ensure contiguous coverage (fill any gaps)
        return self._ensure_contiguous_coverage(merged_chunks, full_text, max_chars, book_id, chapter_id, default_voice_name, default_speed)
    
    def _ensure_contiguous_coverage(
        self,
        chunks: List[Chunk],
        full_text: str,
        max_chars: int,
        book_id: Optional[str],
        chapter_id: Optional[str],
        default_voice_name: Optional[str],
        default_speed: Optional[float],
    ) -> List[Chunk]:
        """
        Ensure chunks have contiguous coverage (no gaps).
        
        If there are gaps, tries to extend chunks or create gap chunks.
        """
        if not chunks:
            return []
        
        contiguous_chunks: List[Chunk] = []
        
        for i, chunk in enumerate(chunks):
            # Determine desired end position
            if i < len(chunks) - 1:
                desired_end = chunks[i + 1].text_start
            else:
                desired_end = len(full_text)
            
            # Check if we need to extend or create gap chunk
            if chunk.text_end < desired_end:
                # There's a gap - check what's in the gap
                gap_text = full_text[chunk.text_end:desired_end]
                gap_size = len(gap_text)
                extended_size = chunk.text_length + gap_size
                
                # If gap is purely whitespace, extend the chunk to include it if possible
                # (whitespace should never become a separate chunk)
                is_pure_whitespace = not gap_text.strip()
                
                if is_pure_whitespace:
                    # Always extend to include pure whitespace gaps
                    # Never remove characters - include whitespace even if it slightly exceeds limit
                    # (The _create_chunk method will handle truncation if absolutely necessary,
                    # but we prefer to include all characters)
                    extended_text = full_text[chunk.text_start:desired_end]
                    extended_chunk = self._create_chunk(
                        extended_text,
                        chunk.text_start,
                        desired_end,
                        len(contiguous_chunks) + 1,
                        book_id,
                        chapter_id,
                        default_voice_name,
                        default_speed,
                    )
                    contiguous_chunks.append(extended_chunk)
                elif extended_size <= max_chars:
                    # Gap has content but fits within limits - extend chunk
                    extended_text = full_text[chunk.text_start:desired_end]
                    extended_chunk = self._create_chunk(
                        extended_text,
                        chunk.text_start,
                        desired_end,
                        len(contiguous_chunks) + 1,
                        book_id,
                        chapter_id,
                        default_voice_name,
                        default_speed,
                    )
                    contiguous_chunks.append(extended_chunk)
                else:
                    # Gap has content and can't fit - create gap chunk(s)
                    contiguous_chunks.append(chunk)
                    
                    if len(gap_text) > max_chars:
                        # Split large gap
                        pos = chunk.text_end
                        while pos < desired_end:
                            gap_chunk_end = min(pos + max_chars, desired_end)
                            gap_chunk_text = full_text[pos:gap_chunk_end]
                            gap_chunk = self._create_chunk(
                                gap_chunk_text,
                                pos,
                                gap_chunk_end,
                                len(contiguous_chunks) + 1,
                                book_id,
                                chapter_id,
                                default_voice_name,
                                default_speed,
                            )
                            contiguous_chunks.append(gap_chunk)
                            pos = gap_chunk_end
                    else:
                        # Single gap chunk
                        gap_chunk = self._create_chunk(
                            gap_text,
                            chunk.text_end,
                            desired_end,
                            len(contiguous_chunks) + 1,
                            book_id,
                            chapter_id,
                            default_voice_name,
                            default_speed,
                        )
                        contiguous_chunks.append(gap_chunk)
            else:
                # No gap - use chunk as-is
                contiguous_chunks.append(chunk)
        
        # Filter out chunks that are purely whitespace
        filtered_chunks: List[Chunk] = []
        
        for chunk in contiguous_chunks:
            chunk_text = full_text[chunk.text_start:chunk.text_end]
            
            # Check if chunk is purely whitespace
            if not chunk_text.strip():
                # Pure whitespace - skip it entirely (will be merged into adjacent chunks)
                logger.debug(f"Skipping pure whitespace chunk at position {chunk.text_start}-{chunk.text_end}")
                continue
            
            # Chunk has content - keep it
            filtered_chunks.append(chunk)
        
        # Re-index chunks after filtering
        for i, chunk in enumerate(filtered_chunks, 1):
            filtered_chunks[i - 1] = Chunk(
                index=i,
                book_id=chunk.book_id,
                text_start=chunk.text_start,
                text_end=chunk.text_end,
                status=chunk.status,
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
        
        return filtered_chunks
    
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
        """Create a Chunk from text and positions."""
        # Safety check: if somehow we exceed max_chars, truncate
        # (This shouldn't happen if merge logic is correct, but better safe)
        # XTTS v2 has a hard 250 char limit - we must respect it
        if len(chunk_text) > 250:
            chunk_text = chunk_text[:250]
            chunk_end = chunk_start + 250
        
        # Analyze metadata
        metadata = self._analyze_chunk_metadata(chunk_text, default_voice_name, default_speed)
        
        return Chunk(
            index=index,
            book_id=book_id or '',
            text_start=chunk_start,
            text_end=chunk_end,
            status=ChunkStatus.PENDING,
            chapter_id=chapter_id,
            path=None,
            generation_time_seconds=None,
            voice_name=metadata.get('voice_name'),
            speed=metadata.get('speed'),
            pre_pause_ms=metadata.get('pre_pause_ms', 0),
            post_pause_ms=metadata.get('post_pause_ms', 0),
            is_dialogue=metadata.get('is_dialogue', False),
            is_scene_break=metadata.get('is_scene_break', False),
        )
    
    def _analyze_chunk_metadata(
        self,
        text: str,
        default_voice_name: Optional[str] = None,
        default_speed: Optional[float] = None,
    ) -> dict:
        """
        Analyze chunk text to determine metadata.
        
        Args:
            text: Chunk text
            default_voice_name: Default voice name
            default_speed: Default speed
            
        Returns:
            Dictionary with metadata fields
        """
        # Detect dialogue
        is_dialogue = self.segmenter.detect_dialogue(text)
        
        # Detect scene breaks (*** or multiple paragraph breaks)
        is_scene_break = '***' in text or text.count('\n\n') >= 2
        
        # Extract speaker hint if dialogue
        voice_name = default_voice_name
        if is_dialogue:
            speaker_hint = self.segmenter.extract_speaker_hint(text)
            if speaker_hint:
                voice_name = speaker_hint
        
        # Set scene break pause
        pre_pause_ms = 0
        if is_scene_break:
            pre_pause_ms = 900
        
        return {
            'voice_name': voice_name,
            'speed': default_speed,
            'pre_pause_ms': pre_pause_ms,
            'post_pause_ms': 0,
            'is_dialogue': is_dialogue,
            'is_scene_break': is_scene_break,
        }
    
    def _detect_scene_breaks(self, chunks: List[Chunk]) -> None:
        """Detect scene breaks between chunks and adjust pauses."""
        for i in range(len(chunks) - 1):
            current = chunks[i]
            next_chunk = chunks[i + 1]
            
            # Check for large gap (scene break)
            gap = next_chunk.text_start - current.text_end
            if gap > 50:  # Large gap suggests scene break
                # Update next chunk's pre_pause
                chunks[i + 1] = Chunk(
                    index=next_chunk.index,
                    book_id=next_chunk.book_id,
                    text_start=next_chunk.text_start,
                    text_end=next_chunk.text_end,
                    status=next_chunk.status,
                    chapter_id=next_chunk.chapter_id,
                    path=next_chunk.path,
                    generation_time_seconds=next_chunk.generation_time_seconds,
                    voice_name=next_chunk.voice_name,
                    speed=next_chunk.speed,
                    pre_pause_ms=max(next_chunk.pre_pause_ms, 900),
                    post_pause_ms=next_chunk.post_pause_ms,
                    is_dialogue=next_chunk.is_dialogue,
                    is_scene_break=True,
                )


