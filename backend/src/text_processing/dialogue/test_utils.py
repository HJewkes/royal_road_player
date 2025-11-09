"""Test utilities for dialogue module."""

import json
from typing import Optional

from src.llm.ollama_client import OllamaClient


class MockOllamaClient:
    """Mock Ollama client for testing.
    
    This class mimics the interface of OllamaClient but doesn't make real HTTP calls.
    Use this in tests to avoid requiring Ollama to be running.
    """
    
    def __init__(self, responses: Optional[list] = None):
        """
        Initialize mock client.
        
        Args:
            responses: Optional list of response strings (in order of calls)
        """
        self.responses = responses or []
        self.call_count = 0
        self.last_prompt = None
        self.last_system = None
        self.last_temperature = None
        self.last_messages = None
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Mock generate method.
        
        Args:
            prompt: User prompt
            system: Optional system prompt
            temperature: Sampling temperature
            
        Returns:
            Mock response
        """
        self.last_prompt = prompt
        self.last_system = system
        
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        
        # Default empty response if no responses configured
        return json.dumps({"characters": []}) if self.call_count == 0 else json.dumps({"dialogue_segments": []})
    
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> str:
        """
        Mock chat method (not used by dialogue module currently).
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            
        Returns:
            Mock response
        """
        self.last_messages = messages
        self.last_temperature = temperature
        return self.generate("", None, temperature)
    
    def check_connection(self) -> bool:
        """Mock connection check - always returns True."""
        return True


def create_mock_character_response(characters: list[dict]) -> str:
    """
    Create a mock character identification response.
    
    Args:
        characters: List of character dictionaries
        
    Returns:
        JSON string response
    """
    return json.dumps({"characters": characters})


def create_mock_dialogue_response(segments: list[dict]) -> str:
    """
    Create a mock dialogue extraction response.
    
    Args:
        segments: List of dialogue segment dictionaries
        
    Returns:
        JSON string response
    """
    return json.dumps({"dialogue_segments": segments})


def get_default_character_response() -> str:
    """Get default character response for testing."""
    return create_mock_character_response([
        {
            "name": "John Smith",
            "aliases": ["John"],
            "traits": [
                {"name": "old", "category": "innate", "confidence": 1.0},
            ],
            "first_mentioned": True,
        },
    ])


def get_default_dialogue_response() -> str:
    """Get default dialogue response for testing."""
    return create_mock_dialogue_response([
        {
            "text": "Hello",
            "speaker": "John Smith",
            "start_pos": 0,
            "end_pos": 5,
            "emotion": {"emotion": "normal", "intensity": 1.0, "confidence": 1.0},
            "speed": {"speed": "normal", "multiplier": 1.0, "confidence": 1.0},
            "confidence": 0.9,
        },
    ])
