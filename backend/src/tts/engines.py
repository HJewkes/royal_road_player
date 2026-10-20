"""TTS engine factory: picks the engine named in settings (XTTS by default)."""

from typing import Optional, Union

from src.config import get_settings
from src.text import chunking_for
from src.tts.chatterbox import ChatterboxEngine
from src.tts.profiles import P4
from src.tts.xtts import XTTSEngine

ENGINES = ("xtts", "chatterbox")

# Chunk i renders with seed 999 + i: the prototype's 1000 + i over 1-based chunks.
CHUNK_SEED_BASE = 999

_xtts: Optional[XTTSEngine] = None
_chatterbox: Optional[ChatterboxEngine] = None


def get_tts_engine(name: Optional[str] = None) -> Union[XTTSEngine, ChatterboxEngine]:
    """Return the engine for `name`, or for `settings.tts_engine` when omitted.

    Chatterbox raises ChatterboxUnavailable on a host with no Chatterbox venv.
    """
    global _xtts, _chatterbox
    name = name or get_settings().tts_engine
    if name == "xtts":
        if _xtts is None:
            _xtts = XTTSEngine()
        return _xtts
    if name == "chatterbox":
        if _chatterbox is None:
            _chatterbox = ChatterboxEngine()
        return _chatterbox
    raise ValueError(f"Unknown TTS engine {name!r}; expected one of {ENGINES}")


def reset_tts_engine() -> None:
    """Free the XTTS model and stop the Chatterbox worker."""
    global _xtts, _chatterbox
    if _xtts is not None:
        _xtts.reset()
        _xtts = None
    if _chatterbox is not None:
        _chatterbox.close()
        _chatterbox = None


def chunk_seed(chunk_index: int) -> int:
    return CHUNK_SEED_BASE + chunk_index


def engine_stamp(name: str) -> dict:
    """The chapter provenance record that `ChunkDiscovery.save_chunks` writes."""
    stamp = {"engine": name, "chunking": chunking_for(name).name}
    if name == "chatterbox":
        stamp["profile"] = P4.name
    return stamp
