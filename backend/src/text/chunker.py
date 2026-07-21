"""Text chunking for TTS synthesis.

Splits normalized text into chunks respecting the XTTS v2 250-character limit.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# XTTS v2 hard character limit
MAX_CHUNK_CHARS = 250


@dataclass
class ChunkResult:
    """Result of chunking with text and position info."""
    index: int  # 1-based chunk index
    text: str
    text_start: int
    text_end: int


class TextChunker:
    """Chunks text for TTS synthesis respecting character limits."""

    # Patterns that shouldn't be split
    PROTECTED_PATTERNS = [
        r'\bunder the\b', r'\bover the\b', r'\bthrough the\b', r'\binto the\b',
        r'\bonto the\b', r'\bfrom the\b', r'\bto the\b', r'\bfor the\b',
        r'\bwith the\b', r'\bby the\b', r'\bat the\b', r'\bin the\b',
        r'\bon the\b', r'\bof the\b', r'\bout of\b', r'\bup to\b',
    ]

    def chunk(self, text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[ChunkResult]:
        """
        Chunk text into segments respecting character limit.

        Args:
            text: Normalized text to chunk
            max_chars: Maximum characters per chunk (default: 250)

        Returns:
            List of ChunkResult objects with text and positions
        """
        if not text or not text.strip():
            return []

        # Split at paragraph breaks first so no chunk spans a paragraph boundary.
        # An internal `."\n\n` (dialogue close + new paragraph) makes XTTS emit a
        # phantom babble outburst at that junction; giving each paragraph its own
        # chunk removes the trigger and yields a natural paragraph pause on concat.
        raw_chunks = []
        for paragraph in re.split(r'\n\s*\n', text):
            paragraph = paragraph.strip()
            if paragraph:
                raw_chunks.extend(self._split_text(paragraph, max_chars))

        # Filter out punctuation-only chunks
        filtered = self._filter_meaningless_chunks(raw_chunks)

        # Create ChunkResult objects with positions
        results = []
        pos = 0

        for chunk_text in filtered:
            clean = self._clean_chunk_end(chunk_text)
            if not clean:
                continue
            results.append(ChunkResult(
                index=len(results) + 1,
                text=clean,
                text_start=pos,
                text_end=pos + len(clean),
            ))
            pos += len(clean)

        return results

    # A trailing quotation mark is never pronounced, yet it triggers a hallucinated
    # outburst at the end of a chunk in XTTS (validated: 3/9 -> 0/9 with it removed).
    _TRAILING_QUOTES = re.compile(r'["“”\'‘’]+\s*$')

    def _clean_chunk_end(self, text: str) -> str:
        """Drop a trailing quotation mark so XTTS doesn't babble at the chunk end."""
        return self._TRAILING_QUOTES.sub('', text.rstrip()).rstrip()

    def _split_text(self, text: str, max_chars: int) -> List[str]:
        """Split text into chunks at natural boundaries."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        pos = 0

        while pos < len(text):
            remaining = text[pos:]
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            chunk = remaining[:max_chars]
            split_at = self._find_split_point(chunk, remaining)

            if split_at is None:
                logger.error(f"Cannot split text at position {pos}: no whitespace found")
                raise ValueError(f"Cannot safely split text: no whitespace in {max_chars} characters")

            chunks.append(text[pos:pos + split_at])
            pos += split_at

        return chunks

    def _find_split_point(self, chunk: str, remaining: str) -> Optional[int]:
        """Find best split point in chunk, searching backwards."""
        # Strategy order: paragraph → sentence → comma → whitespace
        strategies = [
            # Paragraph breaks
            lambda i: i > 0 and chunk[i - 1] == '\n' and chunk[i] == '\n',
            # Sentence endings
            lambda i: i > 0 and chunk[i - 1] in '.!?' and chunk[i] in ' \n\t',
            # Commas/semicolons
            lambda i: i > 0 and chunk[i - 1] in ',;:' and i < len(chunk) and chunk[i] in ' \n\t',
            # Any whitespace
            lambda i: chunk[i] in ' \n\t',
        ]

        for check_fn in strategies:
            for i in range(len(chunk) - 1, 0, -1):
                if check_fn(i):
                    # Check if splitting would break a protected pattern
                    if not self._would_break_pattern(chunk[:i], remaining[i:]):
                        return i + 1

        return None

    def _would_break_pattern(self, before: str, after: str) -> bool:
        """Check if splitting here would break a protected pattern."""
        before_words = ' '.join(before.rstrip().split()[-3:])
        after_words = ' '.join(after.lstrip().split()[:3])
        combined = before_words + ' ' + after_words

        for pattern in self.PROTECTED_PATTERNS:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                match_start_in_before = match.start() < len(before_words)
                match_end_in_after = match.end() > len(before_words) + 1
                if match_start_in_before and match_end_in_after:
                    return True

        return False

    def _filter_meaningless_chunks(self, chunks: List[str]) -> List[str]:
        """Merge punctuation-only chunks with adjacent chunks."""
        if not chunks:
            return []

        filtered = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            if self._is_meaningful(current):
                filtered.append(current)
                i += 1
            else:
                # Merge with previous chunk if it exists
                if filtered:
                    # Check if merging would exceed limit
                    if len(filtered[-1]) + len(current) <= MAX_CHUNK_CHARS:
                        filtered[-1] = filtered[-1] + current
                    else:
                        # Can't merge, keep separate
                        filtered.append(current)
                        logger.warning(f"Keeping punctuation-only chunk (merge would exceed limit)")
                elif i + 1 < len(chunks):
                    # Merge with next chunk
                    next_chunk = chunks[i + 1]
                    if len(current) + len(next_chunk) <= MAX_CHUNK_CHARS:
                        filtered.append(current + next_chunk)
                        i += 2
                        continue
                    else:
                        filtered.append(current)
                else:
                    # Last chunk, keep it
                    filtered.append(current)

                i += 1

        return filtered

    def _is_meaningful(self, text: str) -> bool:
        """Check if text contains at least one word character."""
        # Remove all punctuation and whitespace
        cleaned = re.sub(r'[^\w]', '', text)
        return len(cleaned) > 0


