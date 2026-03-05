"""Speech-to-text service using Whisper for audio validation."""

import hashlib
import json
import logging
import warnings
from pathlib import Path
from typing import Optional

from src.config import get_settings

# Suppress Whisper FP16 warnings on CPU
warnings.filterwarnings("ignore", message=".*FP16 is not supported on CPU.*", category=UserWarning)

try:
    import whisper
except ImportError:
    whisper = None

logger = logging.getLogger(__name__)


class STTService:
    """Service for transcribing audio files using Whisper."""

    def __init__(self, model_size: str = "base"):
        """
        Initialize STT service.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        if whisper is None:
            raise ImportError(
                "openai-whisper is not installed. "
                "Install it with: pip install openai-whisper"
            )

        self.model_size = model_size
        self._model = None
        self.settings = get_settings()
        self.cache_dir = self.settings.cache_dir / "stt"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"STT service initialized with model: {model_size}")

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")
        return self._model

    def _get_audio_hash(self, audio_path: Path) -> str:
        """Generate hash of audio file for caching."""
        with open(audio_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def _get_cache_path(self, audio_path: Path) -> Path:
        """Get cache file path for audio file."""
        audio_hash = self._get_audio_hash(audio_path)
        return self.cache_dir / f"{audio_hash}_{self.model_size}.json"

    def transcribe(
        self,
        audio_path: Path,
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            use_cache: Whether to use cached results

        Returns:
            Transcribed text or None if transcription fails
        """
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        # Check cache
        if use_cache:
            cache_path = self._get_cache_path(audio_path)
            if cache_path.exists():
                try:
                    with open(cache_path) as f:
                        cached = json.load(f)
                    logger.debug(f"Using cached transcription for {audio_path.name}")
                    return cached.get("text")
                except Exception as e:
                    logger.warning(f"Cache read failed: {e}")

        try:
            model = self._load_model()
            logger.debug(f"Transcribing: {audio_path}")

            result = model.transcribe(
                str(audio_path),
                language="en",
                task="transcribe",
                verbose=False,
            )

            text = result.get("text", "").strip()

            # Cache result
            if use_cache:
                try:
                    cache_path = self._get_cache_path(audio_path)
                    with open(cache_path, "w") as f:
                        json.dump({"text": text}, f)
                except Exception as e:
                    logger.warning(f"Cache write failed: {e}")

            logger.debug(f"Transcribed {len(text)} characters")
            return text if text else None

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None


# Singleton instance
_stt: Optional[STTService] = None


def get_stt_service() -> STTService:
    """Get STT service singleton."""
    global _stt
    if _stt is None:
        settings = get_settings()
        _stt = STTService(model_size=settings.whisper_model)
    return _stt


