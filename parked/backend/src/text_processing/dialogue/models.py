"""Data models for dialogue extraction and character identification."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import attr


class TraitCategory(str, Enum):
    """Category of character trait."""
    
    INNATE = "innate"  # Permanent traits: age, nationality, accent, gender, etc.
    TEMPORARY = "temporary"  # Context-dependent: emotional state, physical condition, etc.


@attr.s(auto_attribs=True, frozen=True)
class CharacterTrait:
    """A character trait with category and context."""
    
    name: str  # e.g., "old", "French", "out of breath", "excited"
    category: TraitCategory  # innate or temporary
    context: Optional[str] = None  # Additional context about when/why this trait applies
    confidence: float = 1.0  # Confidence score 0.0-1.0


@attr.s(auto_attribs=True)
class Character:
    """A character identified in the text."""
    
    name: str  # Character name (normalized)
    aliases: List[str] = attr.Factory(list)  # Alternative names, nicknames, titles
    traits: List[CharacterTrait] = attr.Factory(list)  # All traits (innate + temporary)
    first_mentioned_chapter: Optional[str] = None  # Chapter where character first appears
    last_mentioned_chapter: Optional[str] = None  # Most recent chapter
    
    def get_innate_traits(self) -> List[CharacterTrait]:
        """Get only innate (permanent) traits."""
        return [t for t in self.traits if t.category == TraitCategory.INNATE]
    
    def get_temporary_traits(self) -> List[CharacterTrait]:
        """Get only temporary (context-dependent) traits."""
        return [t for t in self.traits if t.category == TraitCategory.TEMPORARY]
    
    def merge_traits(self, new_traits: List[CharacterTrait]) -> None:
        """
        Merge new traits with existing ones, avoiding duplicates.
        
        Args:
            new_traits: New traits to merge in
        """
        existing_names = {t.name.lower() for t in self.traits}
        for trait in new_traits:
            if trait.name.lower() not in existing_names:
                self.traits.append(trait)
                existing_names.add(trait.name.lower())


@attr.s(auto_attribs=True, frozen=True)
class EmotionCue:
    """Emotion or mood cue for dialogue."""
    
    emotion: str  # e.g., "excited", "sad", "angry", "whispering"
    intensity: float = 1.0  # Intensity 0.0-1.0
    confidence: float = 1.0  # Confidence score 0.0-1.0


@attr.s(auto_attribs=True, frozen=True)
class SpeedCue:
    """Speed/pacing cue for dialogue."""
    
    speed: str  # e.g., "fast", "slow", "normal", "urgent"
    multiplier: float = 1.0  # Speed multiplier (0.5-2.0)
    confidence: float = 1.0  # Confidence score 0.0-1.0


@attr.s(auto_attribs=True, frozen=True)
class DialogueSegment:
    """A single dialogue segment with speaker and cues."""
    
    text: str  # The quoted dialogue text (without quotes)
    speaker: Optional[str] = None  # Character name (normalized)
    start_pos: int = 0  # Character position in original text
    end_pos: int = 0  # Character position in original text
    emotion: Optional[EmotionCue] = None  # Emotion/mood cue
    speed: Optional[SpeedCue] = None  # Speed/pacing cue
    confidence: float = 1.0  # Overall confidence score 0.0-1.0
    context_before: Optional[str] = None  # Text before dialogue (for context)
    context_after: Optional[str] = None  # Text after dialogue (for context)


@attr.s(auto_attribs=True)
class ChapterCharacterAnalysis:
    """Character analysis result for a chapter."""
    
    chapter_id: str
    characters: List[Character] = attr.Factory(list)  # Characters found in this chapter
    character_map: Dict[str, Character] = attr.Factory(dict)  # Name -> Character lookup
    
    def get_character(self, name: str) -> Optional[Character]:
        """Get character by name (checks aliases too)."""
        # Direct lookup
        if name in self.character_map:
            return self.character_map[name]
        
        # Check aliases
        name_lower = name.lower()
        for char in self.characters:
            if char.name.lower() == name_lower:
                return char
            if any(alias.lower() == name_lower for alias in char.aliases):
                return char
        
        return None


@attr.s(auto_attribs=True)
class ChapterDialogueAnalysis:
    """Dialogue extraction result for a chapter."""
    
    chapter_id: str
    segments: List[DialogueSegment] = attr.Factory(list)  # All dialogue segments
    characters_used: List[str] = attr.Factory(list)  # Characters who spoke in this chapter


class CharacterRegistry:
    """Registry for tracking characters across chapters."""
    
    def __init__(self):
        """Initialize character registry."""
        self.characters: Dict[str, Character] = {}  # name -> Character
        self.chapter_characters: Dict[str, List[str]] = {}  # chapter_id -> [character_names]
    
    def add_chapter_analysis(self, analysis: ChapterCharacterAnalysis) -> None:
        """
        Add character analysis from a chapter.
        
        Args:
            analysis: Character analysis result
        """
        chapter_id = analysis.chapter_id
        self.chapter_characters[chapter_id] = []
        
        for char in analysis.characters:
            # Check if character already exists
            existing = self.characters.get(char.name)
            
            if existing:
                # Merge traits
                existing.merge_traits(char.traits)
                # Merge aliases
                for alias in char.aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)
                # Update last mentioned
                existing.last_mentioned_chapter = chapter_id
            else:
                # New character
                char.first_mentioned_chapter = chapter_id
                char.last_mentioned_chapter = chapter_id
                self.characters[char.name] = char
            
            self.chapter_characters[chapter_id].append(char.name)
    
    def get_characters_for_chapter(self, chapter_id: str) -> List[Character]:
        """
        Get characters that appear in a chapter.
        
        Args:
            chapter_id: Chapter identifier
            
        Returns:
            List of characters
        """
        char_names = self.chapter_characters.get(chapter_id, [])
        return [self.characters[name] for name in char_names if name in self.characters]
    
    def get_all_characters(self) -> List[Character]:
        """Get all registered characters."""
        return list(self.characters.values())
    
    def get_character(self, name: str) -> Optional[Character]:
        """
        Get character by name (checks aliases).
        
        Args:
            name: Character name or alias
            
        Returns:
            Character or None
        """
        # Direct lookup
        if name in self.characters:
            return self.characters[name]
        
        # Check aliases
        name_lower = name.lower()
        for char in self.characters.values():
            if char.name.lower() == name_lower:
                return char
            if any(alias.lower() == name_lower for alias in char.aliases):
                return char
        
        return None
