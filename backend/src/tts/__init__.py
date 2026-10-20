"""TTS engine module (XTTS v2 by default; the engine is chosen in settings)."""

from src.tts.xtts import XTTSEngine
from src.tts.engines import engine_stamp, get_tts_engine, reset_tts_engine

__all__ = ['XTTSEngine', 'engine_stamp', 'get_tts_engine', 'reset_tts_engine']
