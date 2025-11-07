"""Configuration management."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


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

    # Data Paths
    data_dir: Path = Path("./data")
    books_dir: Path = Path("./data/books")
    audio_dir: Path = Path("./data/books")
    database_path: Path = Path("./data/databases/audiobook.db")

    # Scraper Configuration
    scraper_delay_seconds: int = 2
    scraper_user_agent: str = "Mozilla/5.0 (compatible; AudiobookBot/1.0)"
    scraper_retry_attempts: int = 3

    # Logging
    log_level: str = "INFO"
    log_dir: Path = Path("./logs")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        """Initialize settings and create directories."""
        super().__init__(**kwargs)
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings

