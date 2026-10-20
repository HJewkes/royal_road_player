"""TTS engine factory: picks the engine named in settings (XTTS by default)."""

from typing import Optional

from src.config import get_settings
from src.text import chunking_for
from src.tts.xtts import XTTSEngine

ENGINES = ("xtts", "chatterbox")

_xtts: Optional[XTTSEngine] = None


def get_tts_engine(name: Optional[str] = None) -> XTTSEngine:
    """Return the engine for `name`, or for `settings.tts_engine` when omitted."""
    global _xtts
    name = name or get_settings().tts_engine
    if name == "xtts":
        if _xtts is None:
            _xtts = XTTSEngine()
        return _xtts
    if name == "chatterbox":
        raise NotImplementedError("The Chatterbox engine is not wired into the pipeline yet")
    raise ValueError(f"Unknown TTS engine {name!r}; expected one of {ENGINES}")


def reset_tts_engine() -> None:
    """Free the XTTS singleton's model."""
    global _xtts
    if _xtts is not None:
        _xtts.reset()
        _xtts = None


def engine_stamp(name: str) -> dict:
    """The chapter provenance record that `ChunkDiscovery.save_chunks` writes."""
    return {"engine": name, "chunking": chunking_for(name).name}
