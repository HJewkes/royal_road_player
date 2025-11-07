"""Ollama API client."""

import httpx
from typing import Optional

from src.utils.config import get_settings


class OllamaClient:
    """Client for Ollama API."""

    def __init__(self):
        """Initialize Ollama client."""
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url
        self.model = self.settings.ollama_model
        self.client = httpx.Client(timeout=300.0)  # 5 minute timeout for long generations

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using Ollama.

        Args:
            prompt: User prompt
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system

        response = self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["response"]

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> str:
        """
        Chat completion using Ollama.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature

        Returns:
            Assistant response
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        response = self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]

    def check_connection(self) -> bool:
        """
        Check if Ollama is accessible.

        Returns:
            True if connection successful
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

