"""Tests for dialogue service (with mocks)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.text_processing.dialogue.models import (
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    Character,
    CharacterTrait,
    DialogueSegment,
    TraitCategory,
)
from src.text_processing.dialogue.service import DialogueService


class TestDialogueService:
    """Tests for DialogueService."""
    
    @patch('src.text_processing.dialogue.service.OllamaClient')
    def test_process_chapter_mock(self, mock_ollama_client_class):
        """Test processing a chapter with mocked LLM."""
        # Setup mock
        mock_llm = MagicMock()
        mock_ollama_client_class.return_value = mock_llm
        
        # Mock character identification response
        char_response = {
            "characters": [
                {
                    "name": "John Smith",
                    "aliases": ["John"],
                    "traits": [
                        {
                            "name": "old",
                            "category": "innate",
                            "confidence": 1.0,
                        }
                    ],
                    "first_mentioned": True,
                }
            ]
        }
        
        # Mock dialogue extraction response
        dialogue_response = {
            "dialogue_segments": [
                {
                    "text": "Hello, how are you?",
                    "speaker": "John Smith",
                    "start_pos": 100,
                    "end_pos": 120,
                    "emotion": {
                        "emotion": "normal",
                        "intensity": 1.0,
                        "confidence": 1.0,
                    },
                    "speed": {
                        "speed": "normal",
                        "multiplier": 1.0,
                        "confidence": 1.0,
                    },
                    "confidence": 0.9,
                }
            ]
        }
        
        # Configure mock to return different responses for different calls
        mock_llm.generate.side_effect = [
            json.dumps(char_response),
            json.dumps(dialogue_response),
        ]
        
        # Create service
        service = DialogueService()
        
        # Process chapter
        chapter_text = 'John walked in. "Hello, how are you?" he said.'
        char_analysis, dialogue_analysis = service.process_chapter(
            chapter_text=chapter_text,
            chapter_id="test_ch1",
        )
        
        # Verify results
        assert isinstance(char_analysis, ChapterCharacterAnalysis)
        assert isinstance(dialogue_analysis, ChapterDialogueAnalysis)
        assert len(char_analysis.characters) == 1
        assert len(dialogue_analysis.segments) == 1
        assert dialogue_analysis.segments[0].speaker == "John Smith"
    
    def test_character_registry_tracking(self):
        """Test that character registry tracks characters across chapters."""
        service = DialogueService()
        
        # Mock the LLM services to return predictable results
        with patch.object(service.character_service, 'analyze_characters') as mock_char, \
             patch.object(service.dialogue_service, 'extract_dialogue') as mock_dialogue:
            
            # Setup mocks
            char1 = Character(name="John", traits=[])
            char2 = Character(name="Mary", traits=[])
            
            mock_char.side_effect = [
                ChapterCharacterAnalysis(chapter_id="ch1", characters=[char1]),
                ChapterCharacterAnalysis(chapter_id="ch2", characters=[char2]),
            ]
            
            mock_dialogue.return_value = ChapterDialogueAnalysis(
                chapter_id="ch1",
                segments=[],
            )
            
            # Process first chapter
            service.process_chapter("Text 1", "ch1")
            
            # Process second chapter
            service.process_chapter("Text 2", "ch2")
            
            # Check registry
            registry = service.get_character_registry()
            all_chars = registry.get_all_characters()
            assert len(all_chars) == 2
    
    def test_process_multiple_chapters(self):
        """Test processing multiple chapters."""
        service = DialogueService()
        
        with patch.object(service.character_service, 'analyze_characters') as mock_char, \
             patch.object(service.dialogue_service, 'extract_dialogue') as mock_dialogue:
            
            # Setup mocks
            mock_char.return_value = ChapterCharacterAnalysis(
                chapter_id="ch1",
                characters=[],
            )
            mock_dialogue.return_value = ChapterDialogueAnalysis(
                chapter_id="ch1",
                segments=[],
            )
            
            # Process multiple chapters
            chapters = [
                ("ch1", "Chapter 1 text"),
                ("ch2", "Chapter 2 text"),
            ]
            
            results = service.process_multiple_chapters(chapters)
            
            assert len(results) == 2
            assert "ch1" in results
            assert "ch2" in results
