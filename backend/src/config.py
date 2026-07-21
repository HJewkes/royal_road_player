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
    events_log: Path = Path(__file__).parent.parent.parent / "logs" / "events.jsonl"

    # TTS settings
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    voice_sample_path: str = str(Path(__file__).parent.parent.parent / "data" / "voice_samples" / "british_male_p241.wav")
    tts_language: str = "en"

    # Self-healing synthesis: after each chunk, a vocab-free phoneme model checks for
    # a hallucinated outburst (phantom audio with no matching text) and re-rolls the
    # stochastic take until clean. Adds a phoneme pass per chunk (+~1s) and re-rolls
    # only the ~5-7% that babble. Disable to fall back to a single take.
    verify_synthesis: bool = True
    verify_max_retries: int = 5

    # STT Validation settings
    whisper_model: str = "base"  # cheap first-pass model for defect pre-filtering
    whisper_confirm_model: str = "small"  # stronger model that confirms flagged chunks
    validation_threshold: float = 0.90

    # Pronunciation lexicon: respell hard words so XTTS says them correctly
    pronunciation_lexicon_path: str = str(
        Path(__file__).parent.parent.parent / "data" / "pronunciation_lexicon.json"
    )

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

    # Delivery / podcast feed settings
    # Public base URL under which the feed + mp3s are served (include any secret
    # path token here so URLs are unguessable). Empty disables upload — the feed
    # is still built locally. e.g. "https://pub-xxxx.r2.dev/ab-<token>"
    delivery_base_url: str = ""
    delivery_author: str = "Audiobook Pipeline"
    # Unguessable path segment prefixed to every object key so the (public)
    # bucket's feed + mp3 URLs can't be guessed — the content is the author's
    # paid work, space-shifted for personal use. Empty = no prefix.
    delivery_path_prefix: str = ""
    # R2 bucket for uploads + the S3-compatible endpoint/creds (R2 API token).
    # All four must be set to enable upload; otherwise the feed is local-only.
    r2_bucket: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    class Config:
        env_prefix = "AUDIOBOOK_"
        env_file = str(Path(__file__).parent.parent.parent / ".env")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

