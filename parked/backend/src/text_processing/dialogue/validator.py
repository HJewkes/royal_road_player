"""Validation functions to prevent LLM hallucinations."""

import logging
import re
from typing import List, Optional, Set

import attr

from src.text_processing.dialogue.models import (
    Character,
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    DialogueSegment,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


class DialogueValidator:
    """Validator for dialogue extraction results."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for comparison (handles whitespace, quotes, etc.).
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Normalize whitespace (multiple spaces -> single space)
        text = re.sub(r'\s+', ' ', text)
        # Normalize different quote types
        text = text.replace('"', '"').replace('"', '"')  # Smart quotes -> regular
        text = text.replace(''', "'").replace(''', "'")  # Smart single quotes -> regular
        # Strip leading/trailing whitespace
        text = text.strip()
        return text
    
    @staticmethod
    def find_quoted_text_in_original(original_text: str) -> List[tuple[str, int, int]]:
        """
        Find all quoted text segments in original text.
        
        Args:
            original_text: Original chapter text
            
        Returns:
            List of (quoted_text, start_pos, end_pos) tuples
        """
        quoted_segments = []
        
        # Patterns for different quote types
        patterns = [
            (r'"([^"]+)"', '"'),  # Standard double quotes
            (r''([^']+)'', "'"),  # Single quotes
            (r'[""]([^""]+)[""]', '"'),  # Smart double quotes
            (r'['']([^'']+)['']', "'"),  # Smart single quotes
        ]
        
        for pattern, quote_char in patterns:
            for match in re.finditer(pattern, original_text):
                quoted_text = match.group(1)
                start_pos = match.start(1)  # Start of quoted content (without quotes)
                end_pos = match.end(1)  # End of quoted content (without quotes)
                quoted_segments.append((quoted_text, start_pos, end_pos))
        
        # Remove duplicates (same text at same position)
        seen = set()
        unique_segments = []
        for text, start, end in quoted_segments:
            key = (text, start, end)
            if key not in seen:
                seen.add(key)
                unique_segments.append((text, start, end))
        
        return unique_segments
    
    @staticmethod
    def validate_dialogue_segment(
        segment: DialogueSegment,
        original_text: str,
        tolerance_chars: int = 5,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a dialogue segment matches the original text.
        
        Args:
            segment: Dialogue segment to validate
            original_text: Original chapter text
            tolerance_chars: Tolerance for position mismatch (in characters)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Normalize segment text
        segment_text_normalized = DialogueValidator.normalize_text(segment.text)
        
        if not segment_text_normalized:
            return False, "Dialogue segment text is empty"
        
        # Check if segment text appears in original text
        # Try exact match first
        if segment_text_normalized not in original_text:
            # Try normalized original text
            original_normalized = DialogueValidator.normalize_text(original_text)
            if segment_text_normalized not in original_normalized:
                return False, f"Dialogue text '{segment_text_normalized[:50]}...' not found in original text"
        
        # Validate position range
        if segment.start_pos < 0 or segment.end_pos > len(original_text):
            return False, f"Position range [{segment.start_pos}, {segment.end_pos}] out of bounds"
        
        if segment.start_pos >= segment.end_pos:
            return False, f"Invalid position range: start ({segment.start_pos}) >= end ({segment.end_pos})"
        
        # Check if text at position matches
        text_at_position = original_text[segment.start_pos:segment.end_pos]
        text_at_position_normalized = DialogueValidator.normalize_text(text_at_position)
        
        if segment_text_normalized != text_at_position_normalized:
            # Try to find the actual position
            actual_pos = original_text.find(segment_text_normalized)
            if actual_pos != -1:
                # Found at different position - check if within tolerance
                if abs(actual_pos - segment.start_pos) > tolerance_chars:
                    return False, (
                        f"Text mismatch at position [{segment.start_pos}:{segment.end_pos}]. "
                        f"Expected '{text_at_position_normalized[:50]}...', "
                        f"found '{segment_text_normalized[:50]}...'. "
                        f"Actual position: {actual_pos}"
                    )
            else:
                return False, (
                    f"Text at position [{segment.start_pos}:{segment.end_pos}] "
                    f"does not match segment text"
                )
        
        return True, None
    
    @staticmethod
    def validate_all_dialogue_segments(
        segments: List[DialogueSegment],
        original_text: str,
    ) -> tuple[List[DialogueSegment], List[tuple[DialogueSegment, str]]]:
        """
        Validate all dialogue segments and return valid/invalid lists.
        
        Args:
            segments: List of dialogue segments to validate
            original_text: Original chapter text
            
        Returns:
            Tuple of (valid_segments, [(invalid_segment, error_message), ...])
        """
        valid_segments = []
        invalid_segments = []
        
        # First, find all quoted text in original
        quoted_segments = DialogueValidator.find_quoted_text_in_original(original_text)
        quoted_texts = {DialogueValidator.normalize_text(text) for text, _, _ in quoted_segments}
        
        for segment in segments:
            # Check if segment text is actually quoted in original
            segment_normalized = DialogueValidator.normalize_text(segment.text)
            
            if segment_normalized not in quoted_texts:
                invalid_segments.append((
                    segment,
                    f"Dialogue text '{segment.text[:50]}...' is not quoted in original text"
                ))
                continue
            
            # Validate segment
            is_valid, error_msg = DialogueValidator.validate_dialogue_segment(
                segment,
                original_text,
            )
            
            if is_valid:
                valid_segments.append(segment)
            else:
                invalid_segments.append((segment, error_msg or "Unknown validation error"))
        
        return valid_segments, invalid_segments
    
    @staticmethod
    def find_character_mentions(
        text: str,
        character: Character,
    ) -> List[tuple[str, int]]:
        """
        Find all mentions of a character in text (by name or alias).
        
        Args:
            text: Text to search
            character: Character to find
            
        Returns:
            List of (matched_text, position) tuples
        """
        mentions = []
        
        # Search for character name and aliases
        search_terms = [character.name] + character.aliases
        
        for term in search_terms:
            if not term:
                continue
            
            # Case-insensitive search with word boundaries
            pattern = r'\b' + re.escape(term) + r'\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                mentions.append((match.group(0), match.start()))
        
        return mentions
    
    @staticmethod
    def validate_character_in_chapter(
        character: Character,
        chapter_text: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a character is mentioned in the chapter text.
        
        Args:
            character: Character to validate
            chapter_text: Chapter text to search
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        mentions = DialogueValidator.find_character_mentions(chapter_text, character)
        
        if not mentions:
            return False, (
                f"Character '{character.name}' (aliases: {character.aliases}) "
                f"not mentioned in chapter text"
            )
        
        return True, None
    
    @staticmethod
    def validate_all_characters(
        characters: List[Character],
        chapter_text: str,
    ) -> tuple[List[Character], List[tuple[Character, str]]]:
        """
        Validate all characters and return valid/invalid lists.
        
        Args:
            characters: List of characters to validate
            chapter_text: Chapter text to search
            
        Returns:
            Tuple of (valid_characters, [(invalid_character, error_message), ...])
        """
        valid_characters = []
        invalid_characters = []
        
        for character in characters:
            is_valid, error_msg = DialogueValidator.validate_character_in_chapter(
                character,
                chapter_text,
            )
            
            if is_valid:
                valid_characters.append(character)
            else:
                invalid_characters.append((character, error_msg or "Character not found"))
        
        return valid_characters, invalid_characters
    
    @staticmethod
    def validate_speaker_for_segment(
        segment: DialogueSegment,
        characters: List[Character],
        chapter_text: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a dialogue segment's speaker is valid.
        
        Args:
            segment: Dialogue segment to validate
            characters: List of valid characters
            chapter_text: Chapter text (for context)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not segment.speaker:
            # No speaker is valid (unattributed dialogue)
            return True, None
        
        # Check if speaker matches any character
        speaker_lower = segment.speaker.lower()
        
        for char in characters:
            if char.name.lower() == speaker_lower:
                # Found character - validate it's mentioned in chapter
                is_valid, error_msg = DialogueValidator.validate_character_in_chapter(
                    char,
                    chapter_text,
                )
                if is_valid:
                    return True, None
                else:
                    return False, f"Speaker '{segment.speaker}' not mentioned in chapter: {error_msg}"
            
            # Check aliases
            if any(alias.lower() == speaker_lower for alias in char.aliases):
                # Found alias - validate character is mentioned
                is_valid, error_msg = DialogueValidator.validate_character_in_chapter(
                    char,
                    chapter_text,
                )
                if is_valid:
                    return True, None
                else:
                    return False, f"Speaker '{segment.speaker}' (alias) not mentioned in chapter: {error_msg}"
        
        # Speaker doesn't match any character
        return False, (
            f"Speaker '{segment.speaker}' does not match any identified character. "
            f"Available characters: {[c.name for c in characters]}"
        )
    
    @staticmethod
    def validate_analysis(
        character_analysis: ChapterCharacterAnalysis,
        dialogue_analysis: ChapterDialogueAnalysis,
        chapter_text: str,
    ) -> tuple[ChapterCharacterAnalysis, ChapterDialogueAnalysis, List[str]]:
        """
        Validate both character and dialogue analyses.
        
        Args:
            character_analysis: Character analysis to validate
            dialogue_analysis: Dialogue analysis to validate
            chapter_text: Original chapter text
            
        Returns:
            Tuple of (validated_character_analysis, validated_dialogue_analysis, warnings)
        """
        warnings = []
        
        # Validate characters
        valid_chars, invalid_chars = DialogueValidator.validate_all_characters(
            character_analysis.characters,
            chapter_text,
        )
        
        if invalid_chars:
            for char, error_msg in invalid_chars:
                warnings.append(f"Invalid character '{char.name}': {error_msg}")
                logger.warning(f"Character validation failed: {char.name} - {error_msg}")
        
        # Update character analysis with only valid characters
        validated_char_analysis = ChapterCharacterAnalysis(
            chapter_id=character_analysis.chapter_id,
            characters=valid_chars,
            character_map={char.name: char for char in valid_chars},
        )
        
        # Validate dialogue segments
        valid_segments, invalid_segments = DialogueValidator.validate_all_dialogue_segments(
            dialogue_analysis.segments,
            chapter_text,
        )
        
        if invalid_segments:
            for segment, error_msg in invalid_segments:
                warnings.append(f"Invalid dialogue segment: {error_msg}")
                logger.warning(f"Dialogue validation failed: {error_msg}")
        
        # Validate speakers for valid segments
        speaker_validated_segments = []
        for segment in valid_segments:
            is_valid, error_msg = DialogueValidator.validate_speaker_for_segment(
                segment,
                valid_chars,
                chapter_text,
            )
            
            if is_valid:
                speaker_validated_segments.append(segment)
            else:
                warnings.append(f"Invalid speaker for segment '{segment.text[:50]}...': {error_msg}")
                logger.warning(f"Speaker validation failed: {error_msg}")
                # Keep segment but mark speaker as None (create new immutable segment)
                segment = attr.evolve(
                    segment,
                    speaker=None,  # Remove invalid speaker
                    confidence=segment.confidence * 0.5,  # Reduce confidence
                )
                speaker_validated_segments.append(segment)
        
        # Update dialogue analysis with validated segments
        validated_dialogue_analysis = ChapterDialogueAnalysis(
            chapter_id=dialogue_analysis.chapter_id,
            segments=speaker_validated_segments,
            characters_used=list(set(s.speaker for s in speaker_validated_segments if s.speaker)),
        )
        
        return validated_char_analysis, validated_dialogue_analysis, warnings
