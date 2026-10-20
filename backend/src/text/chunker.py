"""Text chunking for TTS synthesis.

Splits normalized text into chunks sized for the target engine's chunking profile.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkingProfile:
    """How one TTS engine wants its text cut."""
    name: str
    max_chars: int
    strip_trailing_quotes: bool
    prefer_unquoted_sentence_end: bool
    merge_floor: int


XTTS_CHUNKING = ChunkingProfile("xtts-250", 250, True, False, 0)
CHATTERBOX_CHUNKING = ChunkingProfile("chatterbox-450", 450, False, True, 40)

_PROFILES = {"xtts": XTTS_CHUNKING, "chatterbox": CHATTERBOX_CHUNKING}


def chunking_for(engine: str) -> ChunkingProfile:
    """Return the chunking profile for a TTS engine name."""
    try:
        return _PROFILES[engine]
    except KeyError:
        raise ValueError(f"No chunking profile for engine {engine!r}") from None


# XTTS v2 hard character limit, kept for importers
MAX_CHUNK_CHARS = XTTS_CHUNKING.max_chars

# Apostrophes are left out so contractions don't flip the quote state.
_DOUBLE_QUOTES = '"“”'


def _in_quote(text: str) -> bool:
    return sum(text.count(q) for q in _DOUBLE_QUOTES) % 2 == 1


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

    def __init__(self, profile: ChunkingProfile = XTTS_CHUNKING):
        self.profile = profile

    def chunk(self, text: str, max_chars: Optional[int] = None) -> List[ChunkResult]:
        """
        Chunk text into segments respecting character limit.

        Args:
            text: Normalized text to chunk
            max_chars: Maximum characters per chunk (default: the profile's max_chars)

        Returns:
            List of ChunkResult objects with text and positions
        """
        if not text or not text.strip():
            return []
        if max_chars is None:
            max_chars = self.profile.max_chars

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
        cleaned = [c for c in (self._clean_chunk_end(t) for t in filtered) if c]
        if self.profile.merge_floor:
            cleaned = self._merge_short(cleaned, max_chars)

        # Create ChunkResult objects with positions
        results = []
        pos = 0

        for clean in cleaned:
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
        if not self.profile.strip_trailing_quotes:
            return text.strip()
        return self._TRAILING_QUOTES.sub('', text.rstrip()).rstrip()

    def _merge_short(self, chunks: List[str], max_chars: int) -> List[str]:
        """Fold a chunk under the merge floor into its predecessor, across paragraphs."""
        floor = self.profile.merge_floor
        merged: List[str] = []
        for chunk_text in chunks:
            short = len(chunk_text) < floor or (merged and len(merged[-1]) < floor)
            if merged and short and len(merged[-1]) + len(chunk_text) + 1 <= max_chars:
                merged[-1] = merged[-1] + ' ' + chunk_text
            else:
                merged.append(chunk_text)
        return merged

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
        if self.profile.prefer_unquoted_sentence_end:
            split_at = self._find_unquoted_sentence_end(chunk, remaining)
            if split_at is not None:
                return split_at

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

    def _find_unquoted_sentence_end(self, chunk: str, remaining: str) -> Optional[int]:
        """Latest sentence end in the back two thirds of chunk that isn't inside quoted speech."""
        for i in range(len(chunk) - 1, len(chunk) // 3, -1):
            if (chunk[i - 1] in '.!?"”' and chunk[i] == ' '
                    and not _in_quote(chunk[:i])
                    and not self._would_break_pattern(chunk[:i], remaining[i:])):
                return i + 1
        return None

    # A spelled letter's period ("the F. A.") is not a sentence end, so never split after one.
    _SPELLED_LETTER_END = re.compile(r'(?:^|\s)[A-Z]\.$')

    def _would_break_pattern(self, before: str, after: str) -> bool:
        """Check if splitting here would break a protected pattern."""
        if self._SPELLED_LETTER_END.search(before.rstrip()):
            return True
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
                    if len(filtered[-1]) + len(current) <= self.profile.max_chars:
                        filtered[-1] = filtered[-1] + current
                    else:
                        # Can't merge, keep separate
                        filtered.append(current)
                        logger.warning(f"Keeping punctuation-only chunk (merge would exceed limit)")
                elif i + 1 < len(chunks):
                    # Merge with next chunk
                    next_chunk = chunks[i + 1]
                    if len(current) + len(next_chunk) <= self.profile.max_chars:
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


