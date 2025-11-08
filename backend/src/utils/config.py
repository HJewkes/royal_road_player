"""Configuration management."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    This resolves to the directory containing backend/ and frontend/ directories,
    regardless of where the code is executed from.
    """
    # This file is at backend/src/utils/config.py
    # Project root is 3 levels up: backend/src/utils -> backend/src -> backend -> project_root
    return Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings."""

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # TTS Configuration
    tts_engine: str = "coqui"  # Options: coqui, piper
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"  # Best quality - voice cloning
    # Alternative: "tts_models/en/vctk/vits" (multi-speaker, no license)
    tts_speaker: Optional[str] = None  # Speaker reference for XTTS v2 (optional)
    tts_language: str = "en"  # Language code
    tts_speed: float = 1.0  # Speech speed multiplier (0.5-2.0)
    tts_emotion: Optional[str] = None  # Emotion for XTTS v2 (neutral, happy, sad, angry, etc.)

    # Web Application
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    debug: bool = False

    # Data Paths - will be computed relative to project root in __init__
    # These are placeholders for Pydantic validation
    data_dir: Optional[Path] = None
    books_dir: Optional[Path] = None
    audio_dir: Optional[Path] = None
    log_dir: Optional[Path] = None

    # Scraper Configuration
    scraper_delay_seconds: int = 2
    scraper_user_agent: str = "Mozilla/5.0 (compatible; AudiobookBot/1.0)"
    scraper_retry_attempts: int = 3

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        """Initialize settings and create directories."""
        super().__init__(**kwargs)
        # Compute paths relative to project root (not current working directory)
        project_root = get_project_root()
        self.data_dir = project_root / "data"
        self.books_dir = project_root / "data" / "books"
        self.audio_dir = project_root / "data" / "books"
        self.log_dir = project_root / "logs"
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings

