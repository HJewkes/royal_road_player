"""TTS engine wrapper."""

import logging
from pathlib import Path
from typing import Optional

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class TTSEngine:
    """Base class for TTS engines."""

    def __init__(self):
        """Initialize TTS engine."""
        self.settings = get_settings()
        self._model = None
        self._loaded = False

    def load_model(self) -> None:
        """Load TTS model."""
        raise NotImplementedError("Subclass must implement load_model")

    def synthesize(
        self,
        text: str,
        output_path: Path,
        annotations: Optional[list] = None,
        **kwargs,
    ) -> Path:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            annotations: Optional list of annotations for prosody control
            **kwargs: Additional engine-specific parameters

        Returns:
            Path to generated audio file
        """
        raise NotImplementedError("Subclass must implement synthesize")

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


class CoquiTTSEngine(TTSEngine):
    """Coqui TTS engine implementation using XTTS v2."""

    def __init__(self):
        """Initialize Coqui TTS engine."""
        super().__init__()
        self._tts = None

    def load_model(self) -> None:
        """Load Coqui TTS model."""
        if self._loaded:
            logger.info("Coqui TTS model already loaded")
            return

        try:
            from TTS.api import TTS

            logger.info(f"Loading Coqui TTS model: {self.settings.tts_model}")
            logger.info("This may take a few minutes on first run as the model downloads...")

            # Initialize TTS with the specified model
            self._tts = TTS(model_name=self.settings.tts_model, progress_bar=True)
            self._model = self._tts
            self._loaded = True

            logger.info("✅ Coqui TTS model loaded successfully")
        except ImportError:
            raise ImportError(
                "Coqui TTS not installed. Run: make install-tts or pip install TTS>=0.22.0"
            )
        except Exception as e:
            logger.error(f"Failed to load Coqui TTS model: {e}")
            raise

    def synthesize(
        self,
        text: str,
        output_path: Path,
        annotations: Optional[list] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
    ) -> Path:
        """
        Synthesize using Coqui TTS.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            annotations: Optional list of annotations (not yet implemented)
            speaker: Speaker reference for XTTS v2 (overrides config)
            language: Language code (overrides config)
            speed: Speech speed multiplier (overrides config)
            emotion: Emotion for XTTS v2 (overrides config)

        Returns:
            Path to generated audio file
        """
        if not self._loaded:
            self.load_model()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use provided parameters or fall back to config
        speaker = speaker or self.settings.tts_speaker
        language = language or self.settings.tts_language
        speed = speed if speed is not None else self.settings.tts_speed
        emotion = emotion or self.settings.tts_emotion

        try:
            logger.info(f"Generating audio: {output_path.name}")
            logger.info(f"Text length: {len(text)} characters")
            
            # Estimate time (rough: ~50-100 chars/sec on CPU, ~200-500 chars/sec on GPU)
            # This is just a rough estimate for user feedback
            estimated_chars_per_sec = 100  # Conservative CPU estimate
            estimated_time = len(text) / estimated_chars_per_sec
            logger.info(f"Estimated generation time: ~{estimated_time/60:.1f} minutes (rough estimate)")

            # XTTS v2 specific parameters
            if "xtts" in self.settings.tts_model.lower():
                # XTTS v2 requires speaker_wav for voice cloning
                # If no speaker provided, we need to handle this
                kwargs = {
                    "text": text,
                    "file_path": str(output_path),
                    "language": language,
                }

                # XTTS v2 requires speaker_wav - must provide reference audio
                if speaker:
                    kwargs["speaker_wav"] = speaker  # Path to reference audio file
                else:
                    # XTTS v2 doesn't have default speakers like VCTK
                    # We need a reference audio file for voice cloning
                    raise ValueError(
                        "XTTS v2 requires a speaker_wav parameter (reference audio file) for voice cloning. "
                        "Please provide a reference audio file with the --speaker parameter, or use a different model."
                    )
                
                # XTTS v2 may support speed and emotion, but API varies by version
                # Try to add them if the model supports them
                try:
                    if speed != 1.0:
                        kwargs["speed"] = speed
                    if emotion:
                        kwargs["emotion"] = emotion
                except TypeError:
                    # Model doesn't support these parameters, skip them
                    pass

                # Track progress for long texts
                import time
                start_time = time.time()
                self._tts.tts_to_file(**kwargs)
                elapsed = time.time() - start_time
                logger.info(f"Generation completed in {elapsed/60:.2f} minutes ({len(text)/elapsed:.1f} chars/sec)")
            else:
                # For other Coqui models, use standard synthesis
                # Check if model is multi-speaker
                if hasattr(self._tts, 'speakers') and self._tts.speakers:
                    # Multi-speaker model - use first speaker as default if none provided
                    if not speaker:
                        speaker = self._tts.speakers[0]
                        logger.info(f"Using default speaker: {speaker}")
                    
                    # Track progress for long texts
                    import time
                    start_time = time.time()
                    self._tts.tts_to_file(text=text, file_path=str(output_path), speaker=speaker)
                    elapsed = time.time() - start_time
                    logger.info(f"Generation completed in {elapsed/60:.2f} minutes ({len(text)/elapsed:.1f} chars/sec)")
                else:
                    # Single-speaker model
                    import time
                    start_time = time.time()
                    self._tts.tts_to_file(text=text, file_path=str(output_path))
                    elapsed = time.time() - start_time
                    logger.info(f"Generation completed in {elapsed/60:.2f} minutes ({len(text)/elapsed:.1f} chars/sec)")

            logger.info(f"✅ Audio generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to synthesize audio: {e}")
            raise


class PiperTTSEngine(TTSEngine):
    """Piper TTS engine implementation."""

    def load_model(self) -> None:
        """Load Piper TTS model."""
        # TODO: Implement Piper TTS model loading
        raise NotImplementedError("Piper TTS not yet implemented")

    def synthesize(
        self,
        text: str,
        output_path: Path,
        annotations: Optional[list] = None,
        **kwargs,
    ) -> Path:
        """Synthesize using Piper TTS."""
        # TODO: Implement Piper TTS synthesis
        raise NotImplementedError("Piper TTS synthesis not yet implemented")


def get_tts_engine() -> TTSEngine:
    """
    Get TTS engine based on configuration.

    Returns:
        Configured TTS engine instance
    """
    settings = get_settings()
    if settings.tts_engine.lower() == "coqui":
        return CoquiTTSEngine()
    elif settings.tts_engine.lower() == "piper":
        return PiperTTSEngine()
    else:
        raise ValueError(f"Unknown TTS engine: {settings.tts_engine}")
