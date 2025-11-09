"""Data models for text processing."""

import hashlib
from typing import Optional

import attr

from src.text_processing.enums import EventKind, Pacing


@attr.s(auto_attribs=True, frozen=True)
class SegmentMetadata:
    """Metadata for a text segment."""
    is_dialogue: bool = False
    speaker_hint: Optional[str] = None
    pacing: Optional[Pacing] = None
    is_epigraph: bool = False
    voice: Optional[str] = None
    speaker_wav: Optional[str] = None
    language: Optional[str] = None
    pacing_adjustment: Optional[Pacing] = None


@attr.s(auto_attribs=True, frozen=True)
class Segment:
    """A segment of text ready for synthesis."""
    id: str  # Deterministic UUID based on text + position
    text: str  # Ready-for-synthesis text
    meta: SegmentMetadata = attr.Factory(lambda: SegmentMetadata())


@attr.s(auto_attribs=True, frozen=True)
class Event:
    """Non-speech timeline event."""
    kind: EventKind
    ms: int = 0  # Duration in milliseconds (for pauses)


def generate_segment_id(text: str, position: int, voice_hint: Optional[str] = None) -> str:
    """
    Generate deterministic segment ID.
    
    Args:
        text: Segment text
        position: Position in document
        voice_hint: Optional voice hint
        
    Returns:
        Deterministic ID (SHA1 hash)
    """
    content = f"{text}|{position}|{voice_hint or ''}"
    return hashlib.sha1(content.encode('utf-8')).hexdigest()[:16]
