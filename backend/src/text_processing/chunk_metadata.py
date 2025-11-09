"""Chunk metadata model for TTS synthesis."""

from typing import Optional

import attr


@attr.s(auto_attribs=True, frozen=True)
class ChunkMetadata:
    """Metadata for a text chunk."""
    voice_name: Optional[str]
    speed: Optional[float]
    pre_pause_ms: int = 0
    post_pause_ms: int = 0
    is_dialogue: bool = False
    is_scene_break: bool = False

