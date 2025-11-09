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
from src.text_processing.dialogue.validator import DialogueValidator

__all__ = [
    "Character",
    "CharacterRegistry",
    "CharacterTrait",
    "ChapterCharacterAnalysis",
    "ChapterDialogueAnalysis",
    "DialogueSegment",
    "DialogueService",
    "DialogueValidator",
    "EmotionCue",
    "SpeedCue",
    "TraitCategory",
]
