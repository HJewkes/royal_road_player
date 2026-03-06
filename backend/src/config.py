"""Configuration settings for the audiobook system."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Paths
    data_dir: Path = Path(__file__).parent.parent.parent / "data"
    books_dir: Path = Path(__file__).parent.parent.parent / "data" / "books"
    exports_dir: Path = Path(__file__).parent.parent.parent / "exports"
    cache_dir: Path = Path(__file__).parent.parent.parent / "data" / "cache"

    # TTS settings
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    voice_sample_path: str = str(Path(__file__).parent.parent.parent / "data" / "voice_samples" / "british_male_p241.wav")
    tts_language: str = "en"

    # STT Validation settings
    whisper_model: str = "base"
    validation_threshold: float = 0.90

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Processing settings
    enable_background_processor: bool = True
    max_concurrent_chunks: int = 1  # XTTS is GPU-bound, run one at a time

    # Patreon settings
    patreon_session_id: str = ""
    patreon_chapter_pattern: str = r"^(\d+)\.(\d+)\s*-\s*(.+?)(?:\s*\[.*\])?$"

    class Config:
        env_prefix = "AUDIOBOOK_"
        env_file = str(Path(__file__).parent.parent.parent / ".env")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

