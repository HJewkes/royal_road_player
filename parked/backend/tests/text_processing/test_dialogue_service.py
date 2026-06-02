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
from src.text_processing.dialogue.test_utils import (
    MockOllamaClient,
    create_mock_character_response,
    create_mock_dialogue_response,
)


class TestDialogueService:
    """Tests for DialogueService."""
    
    @pytest.mark.unit
    def test_process_chapter_with_mock_client(self):
        """Test processing a chapter with MockOllamaClient."""
        # Create mock responses
        char_response = create_mock_character_response([
            {
                "name": "John Smith",
                "aliases": ["John"],
                "traits": [
                    {"name": "old", "category": "innate", "confidence": 1.0},
                ],
                "first_mentioned": True,
            }
        ])
        
        dialogue_response = create_mock_dialogue_response([
            {
                "text": "Hello, how are you?",
                "speaker": "John Smith",
                "start_pos": 20,
                "end_pos": 40,
                "emotion": {"emotion": "normal", "intensity": 1.0, "confidence": 1.0},
                "speed": {"speed": "normal", "multiplier": 1.0, "confidence": 1.0},
                "confidence": 0.9,
            }
        ])
        
        # Create service with mock client
        mock_client = MockOllamaClient(responses=[char_response, dialogue_response])
        service = DialogueService(llm_client=mock_client)
        
        # Process chapter
        chapter_text = 'John walked in. "Hello, how are you?" he said.'
        char_analysis, dialogue_analysis, warnings = service.process_chapter(
            chapter_text=chapter_text,
            chapter_id="test_ch1",
            validate=False,  # Skip validation for mock test
        )
        
        # Verify results
        assert isinstance(char_analysis, ChapterCharacterAnalysis)
        assert isinstance(dialogue_analysis, ChapterDialogueAnalysis)
        assert isinstance(warnings, list)
        assert len(char_analysis.characters) == 1
        assert len(dialogue_analysis.segments) == 1
        assert dialogue_analysis.segments[0].speaker == "John Smith"
        
        # Verify mock was called
        assert mock_client.call_count == 2
    
    @pytest.mark.unit
    def test_process_chapter_with_fixtures(self, dialogue_service_mocked, sample_chapter_text):
        """Test processing with pytest fixtures."""
        service = dialogue_service_mocked
        
        char_analysis, dialogue_analysis, warnings = service.process_chapter(
            chapter_text=sample_chapter_text,
            chapter_id="test_ch1",
            validate=False,
        )
        
        assert isinstance(char_analysis, ChapterCharacterAnalysis)
        assert isinstance(dialogue_analysis, ChapterDialogueAnalysis)
        assert len(char_analysis.characters) == 2  # John and Mary from fixture
        assert len(dialogue_analysis.segments) == 2
    
    @pytest.mark.unit
    def test_character_registry_tracking(self):
        """Test that character registry tracks characters across chapters."""
        # Use mock client to avoid real LLM calls
        mock_client = MockOllamaClient(responses=[
            create_mock_character_response([{"name": "John", "aliases": [], "traits": [], "first_mentioned": True}]),
            create_mock_dialogue_response([]),
            create_mock_character_response([{"name": "Mary", "aliases": [], "traits": [], "first_mentioned": True}]),
            create_mock_dialogue_response([]),
        ])
        service = DialogueService(llm_client=mock_client)
        
        # Process first chapter
        service.process_chapter("John walked in.", "ch1", validate=False)
        
        # Process second chapter
        service.process_chapter("Mary walked in.", "ch2", validate=False)
        
        # Check registry
        registry = service.get_character_registry()
        all_chars = registry.get_all_characters()
        assert len(all_chars) == 2
    
    @pytest.mark.unit
    def test_process_multiple_chapters(self):
        """Test processing multiple chapters."""
        # Use mock client
        mock_client = MockOllamaClient(responses=[
            create_mock_character_response([]),
            create_mock_dialogue_response([]),
            create_mock_character_response([]),
            create_mock_dialogue_response([]),
        ])
        service = DialogueService(llm_client=mock_client)
        
        # Process multiple chapters
        chapters = [
            ("ch1", "Chapter 1 text"),
            ("ch2", "Chapter 2 text"),
        ]
        
        results = service.process_multiple_chapters(chapters, validate=False)
        
        assert len(results) == 2
        assert "ch1" in results
        assert "ch2" in results
        # Results should be tuples of (char_analysis, dialogue_analysis, warnings)
        assert len(results["ch1"]) == 3
        assert mock_client.call_count == 4  # 2 chapters * 2 passes each
