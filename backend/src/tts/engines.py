"""TTS engine factory: picks the engine named in settings (XTTS by default)."""

from typing import Optional, Union

from src.config import get_settings
from src.text import chunking_for
from src.tts.chatterbox import ChatterboxEngine, ChatterboxUnavailable
from src.tts.profiles import P4, T1, ChatterboxProfile, VllmProfile
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


def render_profile(name: str, profile: Optional[str] = None) -> Union[ChatterboxProfile, VllmProfile, None]:
    """The render profile a chapter runs with, from its stamp's engine and profile.

    XTTS has none, so no early-stop guard. A Chatterbox chapter stamped "t1" was
    rendered through the vLLM batch path and takes T1's threshold.
    """
    if name != "chatterbox":
        return None
    return T1 if profile == T1.name else P4


def get_chapter_engine(discovery, fiction_id: str, book: int, chapter: int, factory=get_tts_engine):
    """(engine name, engine) for the engine a chapter's stamp names.

    Repairs must re-render with the engine the chapter was made with, never the
    active one, or the chapter ends up mixing voices. Raises ChatterboxUnavailable
    when that engine cannot run on this host.
    """
    name = discovery.read_engine_stamp(fiction_id, book, chapter)["engine"]
    try:
        return name, factory(name)
    except ChatterboxUnavailable as exc:
        raise ChatterboxUnavailable(
            f"{fiction_id} b{book}/ch{chapter} was rendered with {name}, which cannot run here: {exc}"
        ) from exc


def chunk_seed(chunk_index: int) -> int:
    return CHUNK_SEED_BASE + chunk_index


def engine_stamp(name: str, batch: bool = False) -> dict:
    """The chapter provenance record that `ChunkDiscovery.save_chunks` writes.

    `batch` marks a chapter rendered through chatterbox-vllm; engine and chunking
    stay the same, so restamping does not clear audio.
    """
    stamp = {"engine": name, "chunking": chunking_for(name).name}
    if name == "chatterbox":
        stamp["profile"] = T1.name if batch else P4.name
    return stamp
