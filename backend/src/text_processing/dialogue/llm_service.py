"""LLM services for dialogue extraction."""

import json
import logging
from typing import List, Optional

from src.llm.ollama_client import OllamaClient
from src.text_processing.dialogue.models import (
    Character,
    CharacterTrait,
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    DialogueSegment,
    EmotionCue,
    SpeedCue,
    TraitCategory,
)
from src.text_processing.dialogue.prompts import (
    CharacterIdentificationPrompt,
    DialogueExtractionPrompt,
)

logger = logging.getLogger(__name__)


class CharacterIdentificationService:
    """Service for first-pass character identification and trait extraction."""
    
    def __init__(self, llm_client: OllamaClient):
        """
        Initialize character identification service.
        
        Args:
            llm_client: Ollama client for LLM calls
        """
        self.llm_client = llm_client
        self.prompt_builder = CharacterIdentificationPrompt()
    
    def analyze_characters(
        self,
        chapter_text: str,
        chapter_id: str,
        previous_characters: Optional[List[Character]] = None,
        context_hint: Optional[str] = None,
        temperature: float = 0.3,  # Lower temperature for more consistent results
    ) -> ChapterCharacterAnalysis:
        """
        Analyze chapter text to identify characters and their traits.
        
        Args:
            chapter_text: Full text of the chapter/scene
            chapter_id: Identifier for this chapter
            previous_characters: Characters from previous chapters (for merging)
            context_hint: Optional context about book/genre
            temperature: LLM temperature (lower = more consistent)
            
        Returns:
            ChapterCharacterAnalysis with identified characters
        """
        logger.info(f"Analyzing characters for chapter {chapter_id}")
        
        # Build prompt
        prompt = self.prompt_builder.create_character_analysis_prompt(
            chapter_text=chapter_text,
            chapter_id=chapter_id,
            previous_characters=previous_characters,
            context_hint=context_hint,
        )
        
        # Call LLM
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system=self.prompt_builder.SYSTEM_PROMPT,
                temperature=temperature,
            )
            
            # Parse JSON response
            # Try to extract JSON from response (might have markdown code blocks)
            json_text = self._extract_json(response)
            data = json.loads(json_text)
            
            # Build character objects
            characters = []
            character_map = {}
            
            for char_data in data.get("characters", []):
                char = self._parse_character(char_data, previous_characters)
                characters.append(char)
                character_map[char.name] = char
                # Also add aliases to map
                for alias in char.aliases:
                    character_map[alias] = char
            
            logger.info(f"Identified {len(characters)} characters in chapter {chapter_id}")
            
            return ChapterCharacterAnalysis(
                chapter_id=chapter_id,
                characters=characters,
                character_map=character_map,
            )
            
        except Exception as e:
            logger.error(f"Error analyzing characters for chapter {chapter_id}: {e}")
            # Return empty analysis on error
            return ChapterCharacterAnalysis(chapter_id=chapter_id)
    
    def _parse_character(
        self,
        char_data: dict,
        previous_characters: Optional[List[Character]] = None,
    ) -> Character:
        """Parse character data from LLM response."""
        name = char_data.get("name", "").strip()
        if not name:
            raise ValueError("Character name is required")
        
        # Check if this character exists in previous chapters
        existing_char = None
        if previous_characters:
            name_lower = name.lower()
            for prev_char in previous_characters:
                if prev_char.name.lower() == name_lower:
                    existing_char = prev_char
                    break
                if any(alias.lower() == name_lower for alias in prev_char.aliases):
                    existing_char = prev_char
                    break
        
        # Create or update character
        if existing_char:
            char = Character(
                name=existing_char.name,  # Keep original name
                aliases=list(set(existing_char.aliases + char_data.get("aliases", []))),
                traits=list(existing_char.traits),  # Start with existing traits
            )
        else:
            char = Character(
                name=name,
                aliases=char_data.get("aliases", []),
                traits=[],
            )
        
        # Parse traits
        for trait_data in char_data.get("traits", []):
            trait = CharacterTrait(
                name=trait_data.get("name", ""),
                category=TraitCategory(trait_data.get("category", "innate")),
                context=trait_data.get("context"),
                confidence=trait_data.get("confidence", 1.0),
            )
            char.traits.append(trait)
        
        return char
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        text = text.strip()
        
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Try to find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return text[start:end]
        
        # Return as-is if no JSON found
        return text


class DialogueExtractionService:
    """Service for second-pass dialogue extraction with speaker identification."""
    
    def __init__(self, llm_client: OllamaClient):
        """
        Initialize dialogue extraction service.
        
        Args:
            llm_client: Ollama client for LLM calls
        """
        self.llm_client = llm_client
        self.prompt_builder = DialogueExtractionPrompt()
    
    def extract_dialogue(
        self,
        chapter_text: str,
        chapter_id: str,
        characters: List[Character],
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        temperature: float = 0.3,  # Lower temperature for more consistent results
    ) -> ChapterDialogueAnalysis:
        """
        Extract dialogue segments with speaker identification and cues.
        
        Args:
            chapter_text: Full text of the chapter/scene
            chapter_id: Identifier for this chapter
            characters: Characters identified in first pass
            context_before: Optional text from previous chapter
            context_after: Optional text from next chapter
            temperature: LLM temperature (lower = more consistent)
            
        Returns:
            ChapterDialogueAnalysis with extracted dialogue segments
        """
        logger.info(f"Extracting dialogue for chapter {chapter_id}")
        
        # Build prompt
        prompt = self.prompt_builder.create_dialogue_extraction_prompt(
            chapter_text=chapter_text,
            chapter_id=chapter_id,
            characters=characters,
            context_before=context_before,
            context_after=context_after,
        )
        
        # Call LLM
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system=self.prompt_builder.SYSTEM_PROMPT,
                temperature=temperature,
            )
            
            # Parse JSON response
            json_text = self._extract_json(response)
            data = json.loads(json_text)
            
            # Build dialogue segments
            segments = []
            characters_used = set()
            
            for seg_data in data.get("dialogue_segments", []):
                segment = self._parse_dialogue_segment(seg_data, chapter_text)
                segments.append(segment)
                if segment.speaker:
                    characters_used.add(segment.speaker)
            
            logger.info(
                f"Extracted {len(segments)} dialogue segments in chapter {chapter_id}, "
                f"{len(characters_used)} speakers identified"
            )
            
            return ChapterDialogueAnalysis(
                chapter_id=chapter_id,
                segments=segments,
                characters_used=list(characters_used),
            )
            
        except Exception as e:
            logger.error(f"Error extracting dialogue for chapter {chapter_id}: {e}")
            # Return empty analysis on error
            return ChapterDialogueAnalysis(chapter_id=chapter_id)
    
    def _parse_dialogue_segment(self, seg_data: dict, chapter_text: str) -> DialogueSegment:
        """Parse dialogue segment data from LLM response."""
        text = seg_data.get("text", "").strip()
        speaker = seg_data.get("speaker")
        if speaker:
            speaker = speaker.strip() or None
        
        start_pos = seg_data.get("start_pos", 0)
        end_pos = seg_data.get("end_pos", len(chapter_text))
        confidence = seg_data.get("confidence", 1.0)
        
        # Parse emotion cue
        emotion_data = seg_data.get("emotion")
        emotion = None
        if emotion_data:
            emotion = EmotionCue(
                emotion=emotion_data.get("emotion", "normal"),
                intensity=emotion_data.get("intensity", 1.0),
                confidence=emotion_data.get("confidence", 1.0),
            )
        
        # Parse speed cue
        speed_data = seg_data.get("speed")
        speed = None
        if speed_data:
            speed = SpeedCue(
                speed=speed_data.get("speed", "normal"),
                multiplier=speed_data.get("multiplier", 1.0),
                confidence=speed_data.get("confidence", 1.0),
            )
        
        # Extract context (text before and after)
        context_before = None
        context_after = None
        if start_pos > 0:
            context_before = chapter_text[max(0, start_pos - 100):start_pos].strip()
        if end_pos < len(chapter_text):
            context_after = chapter_text[end_pos:min(len(chapter_text), end_pos + 100)].strip()
        
        return DialogueSegment(
            text=text,
            speaker=speaker,
            start_pos=start_pos,
            end_pos=end_pos,
            emotion=emotion,
            speed=speed,
            confidence=confidence,
            context_before=context_before,
            context_after=context_after,
        )
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        text = text.strip()
        
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Try to find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return text[start:end]
        
        # Return as-is if no JSON found
        return text
