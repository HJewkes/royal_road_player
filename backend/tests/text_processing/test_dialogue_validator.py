"""Tests for dialogue validator."""

import pytest

from src.text_processing.dialogue.models import (
    Character,
    CharacterTrait,
    DialogueSegment,
    EmotionCue,
    SpeedCue,
    TraitCategory,
)
from src.text_processing.dialogue.validator import DialogueValidator


class TestDialogueValidator:
    """Tests for DialogueValidator."""
    
    def test_normalize_text(self):
        """Test text normalization."""
        # Multiple spaces
        assert DialogueValidator.normalize_text("hello   world") == "hello world"
        # Smart quotes
        assert DialogueValidator.normalize_text('"hello"') == '"hello"'
        assert DialogueValidator.normalize_text('"hello"') == '"hello"'
        # Leading/trailing whitespace
        assert DialogueValidator.normalize_text("  hello  ") == "hello"
    
    def test_find_quoted_text(self):
        """Test finding quoted text in original."""
        text = 'John said "Hello" and Mary replied "Hi there".'
        quoted = DialogueValidator.find_quoted_text_in_original(text)
        
        assert len(quoted) == 2
        assert ("Hello", text.find("Hello"), text.find("Hello") + len("Hello")) in quoted
        assert ("Hi there", text.find("Hi there"), text.find("Hi there") + len("Hi there")) in quoted
    
    def test_validate_dialogue_segment_valid(self):
        """Test validating a valid dialogue segment."""
        text = 'John said "Hello, how are you?"'
        segment = DialogueSegment(
            text="Hello, how are you?",
            speaker="John",
            start_pos=text.find("Hello"),
            end_pos=text.find("Hello") + len("Hello, how are you?"),
        )
        
        is_valid, error = DialogueValidator.validate_dialogue_segment(segment, text)
        assert is_valid
        assert error is None
    
    def test_validate_dialogue_segment_not_found(self):
        """Test validating a dialogue segment that doesn't exist."""
        text = 'John said "Hello"'
        segment = DialogueSegment(
            text="Goodbye",  # Not in text
            speaker="John",
            start_pos=0,
            end_pos=7,
        )
        
        is_valid, error = DialogueValidator.validate_dialogue_segment(segment, text)
        assert not is_valid
        assert error is not None
        assert "not found" in error.lower()
    
    def test_validate_dialogue_segment_wrong_position(self):
        """Test validating a dialogue segment with wrong position."""
        text = 'John said "Hello"'
        segment = DialogueSegment(
            text="Hello",
            speaker="John",
            start_pos=0,  # Wrong position
            end_pos=5,
        )
        
        is_valid, error = DialogueValidator.validate_dialogue_segment(segment, text)
        # Should still validate if text matches (position tolerance)
        # But might warn about position mismatch
        assert is_valid or "mismatch" in error.lower()
    
    def test_validate_all_dialogue_segments(self):
        """Test validating multiple dialogue segments."""
        text = 'John said "Hello" and Mary said "Hi".'
        
        segments = [
            DialogueSegment(text="Hello", speaker="John", start_pos=text.find("Hello"), end_pos=text.find("Hello") + 5),
            DialogueSegment(text="Hi", speaker="Mary", start_pos=text.find("Hi"), end_pos=text.find("Hi") + 2),
            DialogueSegment(text="Not here", speaker="Unknown", start_pos=0, end_pos=8),  # Invalid
        ]
        
        valid, invalid = DialogueValidator.validate_all_dialogue_segments(segments, text)
        
        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0][0].text == "Not here"
    
    def test_find_character_mentions(self):
        """Test finding character mentions in text."""
        char = Character(name="John Smith", aliases=["John", "Mr. Smith"])
        text = "John Smith walked in. John said hello. Mr. Smith left."
        
        mentions = DialogueValidator.find_character_mentions(text, char)
        
        assert len(mentions) == 3
        assert any("John Smith" in m[0] for m in mentions)
        assert any("John" in m[0] for m in mentions)
        assert any("Mr. Smith" in m[0] for m in mentions)
    
    def test_validate_character_in_chapter_valid(self):
        """Test validating a character that exists in chapter."""
        char = Character(name="John")
        text = "John walked into the room."
        
        is_valid, error = DialogueValidator.validate_character_in_chapter(char, text)
        assert is_valid
        assert error is None
    
    def test_validate_character_in_chapter_invalid(self):
        """Test validating a character that doesn't exist in chapter."""
        char = Character(name="John")
        text = "Mary walked into the room."  # No John
        
        is_valid, error = DialogueValidator.validate_character_in_chapter(char, text)
        assert not is_valid
        assert error is not None
        assert "not mentioned" in error.lower()
    
    def test_validate_character_by_alias(self):
        """Test validating character found by alias."""
        char = Character(name="John Smith", aliases=["John"])
        text = "John walked into the room."  # Only alias mentioned
        
        is_valid, error = DialogueValidator.validate_character_in_chapter(char, text)
        assert is_valid
    
    def test_validate_all_characters(self):
        """Test validating multiple characters."""
        chars = [
            Character(name="John"),
            Character(name="Mary"),
            Character(name="Bob"),  # Not in text
        ]
        text = "John and Mary walked into the room."
        
        valid, invalid = DialogueValidator.validate_all_characters(chars, text)
        
        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0][0].name == "Bob"
    
    def test_validate_speaker_for_segment_valid(self):
        """Test validating a valid speaker."""
        char = Character(name="John")
        segment = DialogueSegment(
            text="Hello",
            speaker="John",
            start_pos=0,
            end_pos=5,
        )
        text = "John said 'Hello'."
        
        is_valid, error = DialogueValidator.validate_speaker_for_segment(
            segment,
            [char],
            text,
        )
        assert is_valid
        assert error is None
    
    def test_validate_speaker_for_segment_invalid(self):
        """Test validating an invalid speaker."""
        char = Character(name="John")
        segment = DialogueSegment(
            text="Hello",
            speaker="Bob",  # Not in characters
            start_pos=0,
            end_pos=5,
        )
        text = "John said 'Hello'."
        
        is_valid, error = DialogueValidator.validate_speaker_for_segment(
            segment,
            [char],
            text,
        )
        assert not is_valid
        assert error is not None
    
    def test_validate_speaker_no_speaker(self):
        """Test validating segment with no speaker (valid)."""
        segment = DialogueSegment(
            text="Hello",
            speaker=None,  # Unattributed dialogue
            start_pos=0,
            end_pos=5,
        )
        text = "'Hello' was heard."
        
        is_valid, error = DialogueValidator.validate_speaker_for_segment(
            segment,
            [],
            text,
        )
        assert is_valid  # No speaker is valid
    
    def test_validate_analysis_full(self):
        """Test full validation of analysis."""
        from src.text_processing.dialogue.models import ChapterCharacterAnalysis, ChapterDialogueAnalysis
        
        text = 'John said "Hello" and Mary said "Hi".'
        
        # Create analysis with some invalid items
        char_analysis = ChapterCharacterAnalysis(
            chapter_id="test",
            characters=[
                Character(name="John"),
                Character(name="Bob"),  # Not in text
            ],
            character_map={"John": Character(name="John"), "Bob": Character(name="Bob")},
        )
        
        dialogue_analysis = ChapterDialogueAnalysis(
            chapter_id="test",
            segments=[
                DialogueSegment(
                    text="Hello",
                    speaker="John",
                    start_pos=text.find("Hello"),
                    end_pos=text.find("Hello") + len("Hello"),
                ),
                DialogueSegment(
                    text="Not here",  # Invalid
                    speaker="Mary",
                    start_pos=0,
                    end_pos=8,
                ),
            ],
        )
        
        validated_char, validated_dialogue, warnings = DialogueValidator.validate_analysis(
            char_analysis,
            dialogue_analysis,
            text,
        )
        
        # Should filter out invalid character
        assert len(validated_char.characters) == 1
        assert validated_char.characters[0].name == "John"
        
        # Should filter out invalid dialogue segment
        assert len(validated_dialogue.segments) == 1
        assert validated_dialogue.segments[0].text == "Hello"
        
        # Should have warnings
        assert len(warnings) > 0
