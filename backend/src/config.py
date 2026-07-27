"""Configuration settings for the audiobook system."""

from pathlib import Path
from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class PatreonSeries(BaseModel):
    """A renamed continuation of an ongoing story on the same Patreon feed."""

    offset: int
    title: str


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
    # Chapter post titles look like "7.12 - Compartmental [T3]" and, since the
    # author relaunched the story under a new name, "DoF 1.1 - Celebrity [T3]".
    # Named groups are required: series (optional tag), book, chapter, title.
    patreon_chapter_pattern: str = (
        r"^(?:(?P<series>[A-Za-z]{1,10})\s+)?"
        r"(?P<book>\d+)\.(?P<chapter>\d+)\s*-\s*(?P<title>.+?)(?:\s*\[.*\])?$"
    )
    # Renamed continuations of the same story, keyed by their post-title tag.
    # The author restarts numbering at 1.1 on each rename, so `offset` shifts the
    # book into the local sequence (DoF 1.1 -> book 8) — local book numbers must
    # stay monotonic for the data layout and autopull's discovery floor. `title`
    # is what the reader sees: the book is stored as book 8 but published as
    # "DoF - Book 1". A series owns every local book above its offset.
    patreon_series: dict[str, PatreonSeries] = {
        "DoF": PatreonSeries(offset=7, title="DoF"),
    }

    # Delivery / podcast feed settings
    # Public base URL under which the feed + mp3s are served (include any secret
    # path token here so URLs are unguessable). Empty disables upload — the feed
    # is still built locally. e.g. "https://pub-xxxx.r2.dev/ab-<token>"
    delivery_base_url: str = ""
    delivery_author: str = "Audiobook Pipeline"
    # Collection: several separately-titled series that are really one story,
    # published as a single podcast feed in reading order. Listed oldest-first;
    # a slug with nothing exported yet is skipped, so a series can be listed
    # before it starts. Empty list = one feed per series (the old behaviour).
    delivery_collection_title: str = "Max Best Universe"
    delivery_collection_series: list[str] = [
        "player-manager-a-sports-progression-fantasy",
        "soccer-supremo-a-sports-progression-fantasy",
        "dof",
    ]
    # Extra keys the collection feed is ALSO published at. The phone subscribed
    # to the Soccer Supremo feed before the collection existed; republishing
    # there turns that subscription into the collection with no re-subscribe and
    # no re-download (mp3 keys and guids stay per-series and unchanged).
    delivery_collection_aliases: list[str] = [
        "soccer-supremo-a-sports-progression-fantasy",
    ]
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

