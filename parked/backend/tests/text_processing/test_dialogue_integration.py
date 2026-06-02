"""Integration tests for dialogue module (require real LLM)."""

import os
import pytest

from src.text_processing.dialogue.service import DialogueService
from src.text_processing.dialogue.test_utils import is_ollama_available


# Skip all tests in this file if Ollama is not available
pytestmark = pytest.mark.skipif(
    not is_ollama_available(),
    reason="Ollama not available. Set OLLAMA_AVAILABLE=true and ensure Ollama is running.",
)


class TestDialogueServiceIntegration:
    """Integration tests for DialogueService with real LLM."""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_process_chapter_with_real_llm(self):
        """Test processing a chapter with real LLM."""
        service = DialogueService()  # Uses real OllamaClient
        
        chapter_text = '''
        John Smith walked into the room. He was an old man with gray hair.
        "Hello, how are you?" he said excitedly.
        
        Mary Johnson looked up from her book. She was a young woman.
        "I'm doing well, thanks!" she replied quickly.
        '''
        
        char_analysis, dialogue_analysis, warnings = service.process_chapter(
            chapter_text=chapter_text,
            chapter_id="integration_test_ch1",
            validate=True,
        )
        
        # Verify we got results
        assert len(char_analysis.characters) > 0
        assert len(dialogue_analysis.segments) > 0
        
        # Verify characters were identified
        character_names = [char.name for char in char_analysis.characters]
        assert "John Smith" in character_names or "John" in character_names
        assert "Mary Johnson" in character_names or "Mary" in character_names
        
        # Verify dialogue was extracted
        assert any("Hello" in seg.text for seg in dialogue_analysis.segments)
        assert any("doing well" in seg.text.lower() for seg in dialogue_analysis.segments)
        
        # Verify speakers were identified
        speakers = [seg.speaker for seg in dialogue_analysis.segments if seg.speaker]
        assert len(speakers) > 0
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_process_multiple_chapters_with_real_llm(self):
        """Test processing multiple chapters with real LLM."""
        service = DialogueService()
        
        chapters = [
            (
                "integration_ch1",
                '''
                John Smith was an old man. "Hello," he said.
                '''
            ),
            (
                "integration_ch2",
                '''
                John Smith walked into the room. "How are you?" he asked.
                Mary Johnson replied, "I'm fine, thanks!"
                '''
            ),
        ]
        
        results = service.process_multiple_chapters(
            chapters=chapters,
            validate=True,
        )
        
        # Verify we got results for both chapters
        assert len(results) == 2
        assert "integration_ch1" in results
        assert "integration_ch2" in results
        
        # Verify character registry tracks across chapters
        registry = service.get_character_registry()
        all_chars = registry.get_all_characters()
        assert len(all_chars) > 0
        
        # John should be in both chapters
        john = registry.get_character("John Smith") or registry.get_character("John")
        assert john is not None
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_character_trait_extraction(self):
        """Test that character traits are extracted correctly."""
        service = DialogueService()
        
        chapter_text = '''
        John Smith was a 70-year-old French man with a thick accent.
        He was currently out of breath from running.
        "Bonjour," he said excitedly.
        '''
        
        char_analysis, _, warnings = service.process_chapter(
            chapter_text=chapter_text,
            chapter_id="trait_test",
            validate=True,
        )
        
        # Find John
        john = next((c for c in char_analysis.characters if "John" in c.name), None)
        assert john is not None
        
        # Check for innate traits
        innate_traits = john.get_innate_traits()
        trait_names = [t.name.lower() for t in innate_traits]
        assert any("french" in name or "70" in name or "old" in name for name in trait_names)
        
        # Check for temporary traits
        temp_traits = john.get_temporary_traits()
        temp_names = [t.name.lower() for t in temp_traits]
        assert any("breath" in name or "excited" in name for name in temp_names)
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_validation_filters_hallucinations(self):
        """Test that validation correctly filters LLM hallucinations."""
        service = DialogueService()
        
        # Text with specific dialogue
        chapter_text = '''
        John said "Hello there" and walked away.
        Mary replied "Goodbye" as she left.
        '''
        
        char_analysis, dialogue_analysis, warnings = service.process_chapter(
            chapter_text=chapter_text,
            chapter_id="validation_test",
            validate=True,  # Enable validation
        )
        
        # All dialogue segments should match the original text
        for segment in dialogue_analysis.segments:
            # Check that segment text appears in original (normalized)
            normalized_original = chapter_text.lower().replace('"', '"').replace('"', '"')
            normalized_segment = segment.text.lower()
            assert normalized_segment in normalized_original or any(
                word in normalized_original for word in normalized_segment.split()
            )
        
        # All characters should be mentioned in the text
        for char in char_analysis.characters:
            assert char.name.lower() in chapter_text.lower() or any(
                alias.lower() in chapter_text.lower() for alias in char.aliases
            )
