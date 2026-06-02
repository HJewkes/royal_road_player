"""Tests for LLM services (with mocks)."""

import json

import pytest

from src.text_processing.dialogue.llm_service import (
    CharacterIdentificationService,
    DialogueExtractionService,
)
from src.text_processing.dialogue.test_utils import MockOllamaClient, create_mock_character_response, create_mock_dialogue_response


class TestCharacterIdentificationService:
    """Tests for CharacterIdentificationService."""
    
    @pytest.mark.unit
    def test_analyze_characters_success(self):
        """Test successful character analysis."""
        mock_client = MockOllamaClient(responses=[
            create_mock_character_response([
                {
                    "name": "John Smith",
                    "aliases": ["John"],
                    "traits": [{"name": "old", "category": "innate", "confidence": 1.0}],
                    "first_mentioned": True,
                }
            ])
        ])
        
        service = CharacterIdentificationService(mock_client)
        result = service.analyze_characters(
            chapter_text="John Smith walked in.",
            chapter_id="test_ch1",
        )
        
        assert result.chapter_id == "test_ch1"
        assert len(result.characters) == 1
        assert result.characters[0].name == "John Smith"
        assert mock_client.call_count == 1
    
    @pytest.mark.unit
    def test_analyze_characters_empty_response(self):
        """Test handling empty response."""
        mock_client = MockOllamaClient(responses=[json.dumps({"characters": []})])
        
        service = CharacterIdentificationService(mock_client)
        result = service.analyze_characters(
            chapter_text="Some text.",
            chapter_id="test_ch1",
        )
        
        assert len(result.characters) == 0
    
    @pytest.mark.unit
    def test_analyze_characters_invalid_json(self):
        """Test handling invalid JSON response."""
        mock_client = MockOllamaClient(responses=["not json"])
        
        service = CharacterIdentificationService(mock_client)
        # Should handle gracefully and return empty analysis
        result = service.analyze_characters(
            chapter_text="Some text.",
            chapter_id="test_ch1",
        )
        
        # Should return empty analysis on error
        assert result.chapter_id == "test_ch1"


class TestDialogueExtractionService:
    """Tests for DialogueExtractionService."""
    
    @pytest.mark.unit
    def test_extract_dialogue_success(self):
        """Test successful dialogue extraction."""
        mock_client = MockOllamaClient(responses=[
            create_mock_dialogue_response([
                {
                    "text": "Hello",
                    "speaker": "John",
                    "start_pos": 0,
                    "end_pos": 5,
                    "confidence": 0.9,
                }
            ])
        ])
        
        from src.text_processing.dialogue.models import Character
        
        service = DialogueExtractionService(mock_client)
        result = service.extract_dialogue(
            chapter_text='"Hello" said John.',
            chapter_id="test_ch1",
            characters=[Character(name="John", traits=[])],
        )
        
        assert result.chapter_id == "test_ch1"
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello"
        assert result.segments[0].speaker == "John"
        assert mock_client.call_count == 1
    
    @pytest.mark.unit
    def test_extract_dialogue_empty_response(self):
        """Test handling empty response."""
        mock_client = MockOllamaClient(responses=[json.dumps({"dialogue_segments": []})])
        
        from src.text_processing.dialogue.models import Character
        
        service = DialogueExtractionService(mock_client)
        result = service.extract_dialogue(
            chapter_text="Some text.",
            chapter_id="test_ch1",
            characters=[],
        )
        
        assert len(result.segments) == 0
    
    @pytest.mark.unit
    def test_extract_dialogue_invalid_json(self):
        """Test handling invalid JSON response."""
        mock_client = MockOllamaClient(responses=["not json"])
        
        from src.text_processing.dialogue.models import Character
        
        service = DialogueExtractionService(mock_client)
        # Should handle gracefully and return empty analysis
        result = service.extract_dialogue(
            chapter_text="Some text.",
            chapter_id="test_ch1",
            characters=[],
        )
        
        # Should return empty analysis on error
        assert result.chapter_id == "test_ch1"
