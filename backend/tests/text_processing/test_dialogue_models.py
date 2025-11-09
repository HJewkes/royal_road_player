"""Tests for dialogue models."""

import pytest

from src.text_processing.dialogue.models import (
    Character,
    CharacterRegistry,
    CharacterTrait,
    DialogueSegment,
    EmotionCue,
    SpeedCue,
    TraitCategory,
)


class TestCharacterTrait:
    """Tests for CharacterTrait model."""
    
    def test_innate_trait(self):
        """Test creating an innate trait."""
        trait = CharacterTrait(
            name="old",
            category=TraitCategory.INNATE,
            context="Character is described as elderly",
            confidence=1.0,
        )
        assert trait.name == "old"
        assert trait.category == TraitCategory.INNATE
        assert trait.context == "Character is described as elderly"
        assert trait.confidence == 1.0
    
    def test_temporary_trait(self):
        """Test creating a temporary trait."""
        trait = CharacterTrait(
            name="out of breath",
            category=TraitCategory.TEMPORARY,
            context="After running",
            confidence=0.9,
        )
        assert trait.name == "out of breath"
        assert trait.category == TraitCategory.TEMPORARY


class TestCharacter:
    """Tests for Character model."""
    
    def test_create_character(self):
        """Test creating a character."""
        char = Character(
            name="John Smith",
            aliases=["John", "Mr. Smith"],
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
                CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
            ],
        )
        assert char.name == "John Smith"
        assert len(char.aliases) == 2
        assert len(char.traits) == 2
    
    def test_get_innate_traits(self):
        """Test filtering innate traits."""
        char = Character(
            name="Test",
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
                CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
                CharacterTrait(name="French", category=TraitCategory.INNATE),
            ],
        )
        innate = char.get_innate_traits()
        assert len(innate) == 2
        assert all(t.category == TraitCategory.INNATE for t in innate)
    
    def test_get_temporary_traits(self):
        """Test filtering temporary traits."""
        char = Character(
            name="Test",
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
                CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
                CharacterTrait(name="tired", category=TraitCategory.TEMPORARY),
            ],
        )
        temporary = char.get_temporary_traits()
        assert len(temporary) == 2
        assert all(t.category == TraitCategory.TEMPORARY for t in temporary)
    
    def test_merge_traits(self):
        """Test merging new traits."""
        char = Character(
            name="Test",
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
            ],
        )
        new_traits = [
            CharacterTrait(name="French", category=TraitCategory.INNATE),
            CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
        ]
        char.merge_traits(new_traits)
        assert len(char.traits) == 3
    
    def test_merge_traits_duplicate(self):
        """Test merging doesn't create duplicates."""
        char = Character(
            name="Test",
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
            ],
        )
        new_traits = [
            CharacterTrait(name="old", category=TraitCategory.INNATE),  # Duplicate
            CharacterTrait(name="French", category=TraitCategory.INNATE),
        ]
        char.merge_traits(new_traits)
        assert len(char.traits) == 2  # Should not add duplicate


class TestDialogueSegment:
    """Tests for DialogueSegment model."""
    
    def test_create_dialogue_segment(self):
        """Test creating a dialogue segment."""
        segment = DialogueSegment(
            text="Hello, how are you?",
            speaker="John Smith",
            start_pos=100,
            end_pos=120,
            confidence=0.9,
        )
        assert segment.text == "Hello, how are you?"
        assert segment.speaker == "John Smith"
        assert segment.start_pos == 100
        assert segment.end_pos == 120
        assert segment.confidence == 0.9
    
    def test_dialogue_segment_with_cues(self):
        """Test dialogue segment with emotion and speed cues."""
        emotion = EmotionCue(emotion="excited", intensity=0.8, confidence=0.9)
        speed = SpeedCue(speed="fast", multiplier=1.2, confidence=0.8)
        
        segment = DialogueSegment(
            text="Let's go!",
            speaker="John",
            emotion=emotion,
            speed=speed,
        )
        assert segment.emotion.emotion == "excited"
        assert segment.speed.speed == "fast"
        assert segment.speed.multiplier == 1.2


class TestCharacterRegistry:
    """Tests for CharacterRegistry."""
    
    def test_add_character(self):
        """Test adding a character to registry."""
        from src.text_processing.dialogue.models import ChapterCharacterAnalysis
        
        registry = CharacterRegistry()
        
        char = Character(name="John Smith", traits=[])
        analysis = ChapterCharacterAnalysis(
            chapter_id="ch1",
            characters=[char],
            character_map={"John Smith": char},
        )
        
        registry.add_chapter_analysis(analysis)
        assert len(registry.characters) == 1
        assert "John Smith" in registry.characters
    
    def test_merge_characters(self):
        """Test merging characters across chapters."""
        from src.text_processing.dialogue.models import ChapterCharacterAnalysis
        
        registry = CharacterRegistry()
        
        # First chapter
        char1 = Character(
            name="John Smith",
            traits=[CharacterTrait(name="old", category=TraitCategory.INNATE)],
        )
        analysis1 = ChapterCharacterAnalysis(
            chapter_id="ch1",
            characters=[char1],
            character_map={"John Smith": char1},
        )
        registry.add_chapter_analysis(analysis1)
        
        # Second chapter (same character with new trait)
        char2 = Character(
            name="John Smith",
            traits=[CharacterTrait(name="excited", category=TraitCategory.TEMPORARY)],
        )
        analysis2 = ChapterCharacterAnalysis(
            chapter_id="ch2",
            characters=[char2],
            character_map={"John Smith": char2},
        )
        registry.add_chapter_analysis(analysis2)
        
        # Should have merged traits
        merged_char = registry.get_character("John Smith")
        assert merged_char is not None
        assert len(merged_char.traits) == 2
        assert merged_char.last_mentioned_chapter == "ch2"
    
    def test_get_character_by_alias(self):
        """Test getting character by alias."""
        from src.text_processing.dialogue.models import ChapterCharacterAnalysis
        
        registry = CharacterRegistry()
        
        char = Character(name="John Smith", aliases=["John", "Mr. Smith"])
        analysis = ChapterCharacterAnalysis(
            chapter_id="ch1",
            characters=[char],
            character_map={"John Smith": char},
        )
        registry.add_chapter_analysis(analysis)
        
        # Should find by alias
        found = registry.get_character("John")
        assert found is not None
        assert found.name == "John Smith"
