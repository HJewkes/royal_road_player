"""Text-to-speech modules.

This module contains XTTS v2 TTS generation capabilities:
- TTS engine (XTTS v2)
- Voice registry management
- Audio generation pipeline

For text processing (normalization, chunking, segmentation),
see src.text_processing instead.
"""

from src.tts.engine import TTSEngine, get_tts_engine

__all__ = [
    "TTSEngine",
    "get_tts_engine",
]
