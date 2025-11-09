"""Text processing modules for TTS preparation.

This module provides unified text processing for all text transformations:
- HTML extraction and cleaning
- Text normalization (punctuation, numbers, dates, acronyms)
- Segmentation into breath-groups
- Chunking for TTS generation
- Chunk metadata for voice/pacing hints
"""

from src.text_processing.chunk_metadata import ChunkMetadata
from src.text_processing.config import TextProcessingConfig
from src.text_processing.models import Segment, SegmentMetadata, Event, generate_segment_id
from src.text_processing.enums import EventKind, Pacing
from src.text_processing.normalizer import TextNormalizer
from src.text_processing.segmenter import TextSegmenter
from src.text_processing.chunker import TextChunker
from src.text_processing.processor import (
    UnifiedTextProcessor,
    ProcessingConfig,
    process_html_for_storage,
    process_text_for_tts,
    validate_text_for_tts,
)

__all__ = [
    # Core classes
    'TextProcessingConfig',
    'TextNormalizer',
    'TextSegmenter',
    'TextChunker',
    'UnifiedTextProcessor',
    # Models
    'ChunkMetadata',
    'Segment',
    'SegmentMetadata',
    'Event',
    'EventKind',
    'Pacing',
    'generate_segment_id',
    # Processing config
    'ProcessingConfig',
    # Convenience functions
    'process_html_for_storage',
    'process_text_for_tts',
    'validate_text_for_tts',
]
