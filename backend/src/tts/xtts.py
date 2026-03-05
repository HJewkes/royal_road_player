"""XTTS v2 TTS engine implementation.

Simplified version focused on XTTS v2 only.
"""

import gc
import logging
import os
import time
from pathlib import Path
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)

# Enable MPS fallback to CPU for unsupported operations
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


class XTTSEngine:
    """XTTS v2 TTS engine."""

    def __init__(self, voice_sample: Optional[str] = None):
        """
        Initialize TTS engine.

        Args:
            voice_sample: Path to voice sample WAV file for cloning
        """
        self.settings = get_settings()
        self.voice_sample = voice_sample or self.settings.voice_sample_path
        self._tts = None
        self._device = None
        self._loaded = False
        self._chunks_generated = 0

    def load_model(self) -> None:
        """Load XTTS v2 model."""
        if self._loaded:
            return

        try:
            from TTS.api import TTS

            logger.info(f"Loading XTTS v2 model: {self.settings.tts_model}")

            # Detect device
            self._device = self._detect_device()

            # Initialize TTS
            self._tts = TTS(
                model_name=self.settings.tts_model,
                gpu=False,
                progress_bar=True
            )

            # Move to device
            if self._device != "cpu":
                try:
                    self._tts.to(self._device)
                    logger.info(f"✅ Model moved to {self._device.upper()}")
                except Exception as e:
                    logger.warning(f"Failed to use {self._device}, falling back to CPU: {e}")
                    self._device = "cpu"
                    self._tts.to("cpu")

            self._loaded = True
            logger.info(f"✅ XTTS v2 model loaded on {self._device.upper()}")

        except ImportError as e:
            logger.error(f"TTS import error: {e}")
            raise ImportError(f"Coqui TTS not installed or incompatible. Error: {e}. Run: pip install TTS>=0.21.0")
        except Exception as e:
            logger.error(f"TTS initialization error: {type(e).__name__}: {e}")
            raise

    def _detect_device(self) -> str:
        """Detect best available device."""
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("CUDA GPU detected")
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                logger.info("Apple Silicon MPS detected")
                return "mps"
        except Exception as e:
            logger.warning(f"Device detection error: {e}")

        logger.info("Using CPU")
        return "cpu"

    def synthesize(
        self,
        text: str,
        output_path: Path,
        speed: float = 1.0,
    ) -> tuple[Path, float]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize (max 250 chars for XTTS v2)
            output_path: Path to save audio file
            speed: Speech speed multiplier

        Returns:
            Tuple of (output_path, generation_time_seconds)
        """
        if not self._loaded:
            self.load_model()

        if not self.voice_sample:
            raise ValueError("Voice sample path required for XTTS v2")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Preprocess text
        text = self._preprocess_text(text)

        logger.info(f"Generating: {output_path.name} ({len(text)} chars)")

        try:
            start_time = time.time()

            # Synthesize with retry on MPS failure
            try:
                self._tts.tts_to_file(
                    text=text,
                    file_path=str(output_path),
                    language="en",
                    speaker_wav=self.voice_sample,
                    speed=speed,
                )
            except Exception as e:
                if self._device == "mps" and self._is_mps_error(str(e)):
                    logger.warning(f"MPS error, retrying on CPU: {e}")
                    self._tts.to("cpu")
                    self._device = "cpu"
                    self._tts.tts_to_file(
                        text=text,
                        file_path=str(output_path),
                        language="en",
                        speaker_wav=self.voice_sample,
                        speed=speed,
                    )
                else:
                    raise

            elapsed = time.time() - start_time
            self._chunks_generated += 1

            # Clear GPU cache periodically
            if self._chunks_generated % 10 == 0:
                self._clear_cache()

            logger.info(f"✅ Generated in {elapsed:.2f}s")
            return output_path, elapsed

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for TTS."""
        # Handle abbreviations that cause issues
        replacements = [
            ("Mr.", "Mister"),
            ("Mrs.", "Misses"),
            ("Dr.", "Doctor"),
            ("vs.", "versus"),
            ("St.", "Saint"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)

        # Add padding after last word to prevent truncation
        text = text.rstrip()
        if text and text[-1] in '.!?,;:':
            text = text[:-1] + ' ' + text[-1]

        return text

    def _is_mps_error(self, error_msg: str) -> bool:
        """Check if error is a known MPS limitation."""
        mps_indicators = ["65536", "channels", "MPS", "mps"]
        return any(indicator in error_msg for indicator in mps_indicators)

    def _clear_cache(self) -> None:
        """Clear GPU cache to prevent memory buildup."""
        try:
            import torch
            gc.collect()

            if self._device == "cuda":
                torch.cuda.empty_cache()
            elif self._device == "mps" and hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()

            logger.debug("Cleared GPU cache")
        except Exception as e:
            logger.debug(f"Cache clear failed: {e}")

    def reset(self) -> None:
        """Reset model to free memory."""
        if not self._loaded:
            return

        logger.info("Resetting TTS engine...")

        try:
            import torch
            gc.collect()

            del self._tts
            self._tts = None
            self._loaded = False
            self._chunks_generated = 0

            if self._device == "cuda":
                torch.cuda.empty_cache()
            elif self._device == "mps" and hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()

            gc.collect()
            logger.info("✅ TTS engine reset complete")

        except Exception as e:
            logger.warning(f"Reset error: {e}")
            self._tts = None
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


# Singleton instance
_engine: Optional[XTTSEngine] = None


def get_tts_engine() -> XTTSEngine:
    """Get TTS engine singleton."""
    global _engine
    if _engine is None:
        _engine = XTTSEngine()
    return _engine


def reset_tts_engine() -> None:
    """Reset TTS engine singleton."""
    global _engine
    if _engine is not None:
        _engine.reset()
        _engine = None


