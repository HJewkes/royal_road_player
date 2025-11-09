"""Main dialogue service orchestrating two-pass LLM approach."""

import logging
from typing import Dict, List, Optional

from src.llm.ollama_client import OllamaClient
from src.text_processing.dialogue.llm_service import (
    CharacterIdentificationService,
    DialogueExtractionService,
)
from src.text_processing.dialogue.models import (
    Character,
    CharacterRegistry,
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    DialogueSegment,
)

logger = logging.getLogger(__name__)


class DialogueService:
    """Main service for dialogue extraction using two-pass LLM approach."""
    
    def __init__(self, llm_client: Optional[OllamaClient] = None):
        """
        Initialize dialogue service.
        
        Args:
            llm_client: Optional Ollama client (creates new one if not provided)
        """
        self.llm_client = llm_client or OllamaClient()
        self.character_service = CharacterIdentificationService(self.llm_client)
        self.dialogue_service = DialogueExtractionService(self.llm_client)
        self.character_registry = CharacterRegistry()
    
    def process_chapter(
        self,
        chapter_text: str,
        chapter_id: str,
        previous_chapter_text: Optional[str] = None,
        next_chapter_text: Optional[str] = None,
        context_hint: Optional[str] = None,
        temperature: float = 0.3,
    ) -> tuple[ChapterCharacterAnalysis, ChapterDialogueAnalysis]:
        """
        Process a chapter through two-pass LLM analysis.
        
        Args:
            chapter_text: Full text of the chapter
            chapter_id: Unique identifier for this chapter
            previous_chapter_text: Optional text from previous chapter (for continuity)
            next_chapter_text: Optional text from next chapter (for continuity)
            context_hint: Optional context about book/genre
            temperature: LLM temperature (lower = more consistent)
            
        Returns:
            Tuple of (character_analysis, dialogue_analysis)
        """
        logger.info(f"Processing chapter {chapter_id} with two-pass LLM analysis")
        
        # Get previous characters for merging
        previous_characters = self.character_registry.get_all_characters()
        
        # Pass 1: Character identification and trait extraction
        logger.info(f"Pass 1: Character identification for chapter {chapter_id}")
        character_analysis = self.character_service.analyze_characters(
            chapter_text=chapter_text,
            chapter_id=chapter_id,
            previous_characters=previous_characters if previous_characters else None,
            context_hint=context_hint,
            temperature=temperature,
        )
        
        # Update registry with new character analysis
        self.character_registry.add_chapter_analysis(character_analysis)
        
        # Pass 2: Dialogue extraction with speaker identification
        logger.info(f"Pass 2: Dialogue extraction for chapter {chapter_id}")
        dialogue_analysis = self.dialogue_service.extract_dialogue(
            chapter_text=chapter_text,
            chapter_id=chapter_id,
            characters=character_analysis.characters,
            context_before=previous_chapter_text,
            context_after=next_chapter_text,
            temperature=temperature,
        )
        
        logger.info(
            f"Completed processing chapter {chapter_id}: "
            f"{len(character_analysis.characters)} characters, "
            f"{len(dialogue_analysis.segments)} dialogue segments"
        )
        
        return character_analysis, dialogue_analysis
    
    def process_multiple_chapters(
        self,
        chapters: List[tuple[str, str]],  # List of (chapter_id, chapter_text)
        context_hint: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, tuple[ChapterCharacterAnalysis, ChapterDialogueAnalysis]]:
        """
        Process multiple chapters sequentially (maintains character registry across chapters).
        
        Args:
            chapters: List of (chapter_id, chapter_text) tuples
            context_hint: Optional context about book/genre
            temperature: LLM temperature
            
        Returns:
            Dictionary mapping chapter_id to (character_analysis, dialogue_analysis)
        """
        results = {}
        
        for i, (chapter_id, chapter_text) in enumerate(chapters):
            # Get context from adjacent chapters
            previous_text = None
            next_text = None
            
            if i > 0:
                prev_id, previous_text = chapters[i - 1]
            if i < len(chapters) - 1:
                next_id, next_text = chapters[i + 1]
            
            # Process chapter
            char_analysis, dialogue_analysis = self.process_chapter(
                chapter_text=chapter_text,
                chapter_id=chapter_id,
                previous_chapter_text=previous_text,
                next_chapter_text=next_text,
                context_hint=context_hint,
                temperature=temperature,
            )
            
            results[chapter_id] = (char_analysis, dialogue_analysis)
        
        return results
    
    def get_character_registry(self) -> CharacterRegistry:
        """Get the character registry."""
        return self.character_registry
    
    def get_dialogue_segments_for_chapter(self, chapter_id: str) -> List[DialogueSegment]:
        """
        Get dialogue segments for a chapter (requires chapter to be processed first).
        
        Args:
            chapter_id: Chapter identifier
            
        Returns:
            List of dialogue segments
        """
        # This would require storing dialogue analyses, which we can add if needed
        # For now, this is a placeholder
        logger.warning(
            f"get_dialogue_segments_for_chapter not yet implemented. "
            f"Process chapter {chapter_id} first using process_chapter()."
        )
        return []
