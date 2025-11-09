"""Enums for text processing categorical values."""

from enum import Enum


class EventKind(str, Enum):
    """Type of non-speech timeline event."""
    PAUSE = 'pause'
    SCENE_BREAK = 'scene_break'
    EPIGRAPH_START = 'epigraph_start'
    EPIGRAPH_END = 'epigraph_end'
    VOICE_SWITCH = 'voice_switch'


class Pacing(str, Enum):
    """Text pacing hint."""
    NORMAL = 'normal'
    SLOW = 'slow'
    FAST = 'fast'

