"""Dialogue extraction and speaker identification module."""

from src.text_processing.dialogue.models import (
    Character,
    CharacterRegistry,
    CharacterTrait,
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    DialogueSegment,
    EmotionCue,
    SpeedCue,
    TraitCategory,
)
from src.text_processing.dialogue.service import DialogueService

__all__ = [
    "Character",
    "CharacterRegistry",
    "CharacterTrait",
    "ChapterCharacterAnalysis",
    "ChapterDialogueAnalysis",
    "DialogueSegment",
    "DialogueService",
    "EmotionCue",
    "SpeedCue",
    "TraitCategory",
]
