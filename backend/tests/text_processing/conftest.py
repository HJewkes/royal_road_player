"""Pytest fixtures for dialogue tests."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.text_processing.dialogue.models import (
    ChapterCharacterAnalysis,
    ChapterDialogueAnalysis,
    Character,
    CharacterTrait,
    DialogueSegment,
    EmotionCue,
    SpeedCue,
    TraitCategory,
)


@pytest.fixture
def mock_ollama_client():
    """Create a mocked OllamaClient."""
    with patch('src.text_processing.dialogue.service.OllamaClient') as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_character_response():
    """Sample character identification response."""
    return {
        "characters": [
            {
                "name": "John Smith",
                "aliases": ["John"],
                "traits": [
                    {
                        "name": "old",
                        "category": "innate",
                        "confidence": 1.0,
                    },
                    {
                        "name": "excited",
                        "category": "temporary",
                        "confidence": 0.9,
                    },
                ],
                "first_mentioned": True,
            },
            {
                "name": "Mary Johnson",
                "aliases": ["Mary"],
                "traits": [
                    {
                        "name": "young",
                        "category": "innate",
                        "confidence": 1.0,
                    },
                ],
                "first_mentioned": True,
            },
        ]
    }


@pytest.fixture
def sample_dialogue_response():
    """Sample dialogue extraction response."""
    return {
        "dialogue_segments": [
            {
                "text": "Hello, how are you?",
                "speaker": "John Smith",
                "start_pos": 20,
                "end_pos": 40,
                "emotion": {
                    "emotion": "excited",
                    "intensity": 0.8,
                    "confidence": 0.9,
                },
                "speed": {
                    "speed": "normal",
                    "multiplier": 1.0,
                    "confidence": 1.0,
                },
                "confidence": 0.9,
            },
            {
                "text": "I'm doing well, thanks!",
                "speaker": "Mary Johnson",
                "start_pos": 50,
                "end_pos": 75,
                "emotion": {
                    "emotion": "happy",
                    "intensity": 0.7,
                    "confidence": 0.8,
                },
                "speed": {
                    "speed": "fast",
                    "multiplier": 1.2,
                    "confidence": 0.9,
                },
                "confidence": 0.85,
            },
        ]
    }


@pytest.fixture
def mock_llm_responses(mock_ollama_client, sample_character_response, sample_dialogue_response):
    """Configure mock LLM to return sample responses."""
    mock_ollama_client.generate.side_effect = [
        json.dumps(sample_character_response),
        json.dumps(sample_dialogue_response),
    ]
    return mock_ollama_client


@pytest.fixture
def sample_chapter_text():
    """Sample chapter text with dialogue."""
    return '''John Smith walked into the room. "Hello, how are you?" he said excitedly.

Mary Johnson looked up from her book. "I'm doing well, thanks!" she replied quickly.'''


@pytest.fixture
def sample_characters():
    """Sample Character objects."""
    return [
        Character(
            name="John Smith",
            aliases=["John"],
            traits=[
                CharacterTrait(name="old", category=TraitCategory.INNATE),
                CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
            ],
        ),
        Character(
            name="Mary Johnson",
            aliases=["Mary"],
            traits=[
                CharacterTrait(name="young", category=TraitCategory.INNATE),
            ],
        ),
    ]


@pytest.fixture
def sample_dialogue_segments():
    """Sample DialogueSegment objects."""
    return [
        DialogueSegment(
            text="Hello, how are you?",
            speaker="John Smith",
            start_pos=20,
            end_pos=40,
            emotion=EmotionCue(emotion="excited", intensity=0.8),
            speed=SpeedCue(speed="normal", multiplier=1.0),
            confidence=0.9,
        ),
        DialogueSegment(
            text="I'm doing well, thanks!",
            speaker="Mary Johnson",
            start_pos=50,
            end_pos=75,
            emotion=EmotionCue(emotion="happy", intensity=0.7),
            speed=SpeedCue(speed="fast", multiplier=1.2),
            confidence=0.85,
        ),
    ]


@pytest.fixture
def dialogue_service_mocked(mock_llm_responses):
    """Create DialogueService with mocked LLM."""
    from src.text_processing.dialogue.service import DialogueService
    
    service = DialogueService()
    return service
