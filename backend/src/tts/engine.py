"""XTTS v2 TTS engine implementation."""

import logging
import os
import time
import wave
import array
from pathlib import Path
from typing import Optional

from src.tts.model_registry import get_model_registry, FineTunedModel
from src.utils.config import get_settings

logger = logging.getLogger(__name__)

# Enable MPS fallback to CPU for unsupported operations (prevents warnings)
# This allows PyTorch to automatically fall back to CPU when MPS has limitations
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


class TTSEngine:
    """XTTS v2 TTS engine."""

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize TTS engine.
        
        Args:
            model_name: Optional fine-tuned model name (defaults to 'default')
        """
        self.settings = get_settings()
        self._tts = None
        self._loaded = False
        self.model_name = model_name or "default"
        self.model_registry = get_model_registry()
        self.current_model: Optional[FineTunedModel] = None
        
        # Set CPU thread count if specified
        if self.settings.tts_num_threads is not None:
            try:
                import torch
                torch.set_num_threads(self.settings.tts_num_threads)
                logger.info(f"Set PyTorch thread count to {self.settings.tts_num_threads}")
            except Exception as e:
                logger.warning(f"Failed to set thread count: {e}")

    def load_model(self, model_name: Optional[str] = None) -> None:
        """
        Load XTTS v2 model.
        
        Args:
            model_name: Optional model name to load (overrides instance model_name)
        """
        # Update model name if provided
        if model_name is not None:
            self.model_name = model_name
        
        # Get model from registry
        model = self.model_registry.get_model(self.model_name)
        if model is None:
            logger.warning(f"Model '{self.model_name}' not found, using default")
            model = self.model_registry.get_model("default")
            if model is None:
                raise ValueError("Default model not found in registry")
        
        # Check if we need to reload (different model)
        if self._loaded and self.current_model and self.current_model.name == model.name:
            logger.info(f"TTS model '{model.name}' already loaded")
            return
        
        self.current_model = model

        try:
            from TTS.api import TTS

            # Get model path from registry
            model_path = self.model_registry.get_model_path(model)
            logger.info(f"Loading TTS model: {model.name} ({model_path})")
            logger.info(f"Description: {model.description or 'No description'}")
            logger.info("This may take a few minutes on first run as the model downloads...")

            # Check for GPU/MPS availability and determine device
            use_gpu = self.settings.tts_gpu
            device = None
            
            if use_gpu:
                try:
                    import torch
                    if torch.cuda.is_available():
                        device = "cuda"
                        logger.info("✅ CUDA GPU detected - using GPU acceleration")
                    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                        device = "mps"
                        logger.info("✅ Apple Silicon MPS detected - using GPU acceleration")
                    else:
                        logger.warning("TTS_GPU=true but no GPU/MPS available, falling back to CPU")
                        device = "cpu"
                except Exception as e:
                    logger.warning(f"Error checking GPU availability: {e}, using CPU")
                    device = "cpu"
            else:
                device = "cpu"
                logger.info("Using CPU mode (set TTS_GPU=true in .env to enable GPU/MPS)")

            # Initialize TTS with the model from registry
            # Note: gpu parameter is deprecated, use device parameter instead
            self._tts = TTS(
                model_name=model_path,
                gpu=False,  # Set to False, we'll use .to(device) instead
                progress_bar=True
            )
            
            # Move model to appropriate device
            if device and device != "cpu":
                try:
                    self._tts.to(device)
                    logger.info(f"✅ Moved TTS model to {device.upper()} device")
                except Exception as e:
                    error_msg = str(e)
                    # Check for MPS channel limit error - common on Apple Silicon
                    if "mps" in device.lower() and ("65536" in error_msg or "channels" in error_msg.lower()):
                        logger.warning(
                            f"MPS device error detected: {error_msg}. "
                            "This is a known MPS limitation. Falling back to CPU."
                        )
                    else:
                        logger.warning(f"Failed to move model to {device}: {e}, using CPU")
                    device = "cpu"
                    # Try moving to CPU
                    try:
                        self._tts.to("cpu")
                        logger.info("✅ Moved TTS model to CPU device")
                    except Exception as cpu_error:
                        logger.error(f"Failed to move model to CPU: {cpu_error}")
                        raise
            
            self._model = self._tts
            self._device = device
            self._loaded = True

            device_info = device.upper() if device else "CPU"
            logger.info(f"✅ TTS model '{model.name}' loaded successfully on {device_info}")
        except ImportError:
            raise ImportError(
                "Coqui TTS not installed. Run: make install-tts or pip install TTS>=0.22.0"
            )
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            raise

    def synthesize(
        self,
        text: str,
        output_path: Path,
        annotations: Optional[list] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,  # Kept for API compatibility, but always "en"
        speed: Optional[float] = None,
    ) -> Path:
        """
        Synthesize text to speech using XTTS v2.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            annotations: Optional list of annotations (not yet implemented)
            speaker: Speaker reference WAV file path (overrides config)
            language: Language code (ignored, always "en")
            speed: Speech speed multiplier (overrides config)

        Returns:
            Path to generated audio file
        """
        if not self._loaded:
            self.load_model()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use provided parameters or fall back to config
        speaker = speaker or self.settings.tts_speaker
        speed = speed if speed is not None else self.settings.tts_speed
        # Language is always English
        language = "en"

        try:
            logger.info(f"Generating audio: {output_path.name}")
            logger.info(f"Text length: {len(text)} characters")
            
            # Estimate time (rough: ~50-100 chars/sec on CPU, ~200-500 chars/sec on GPU)
            estimated_chars_per_sec = 100  # Conservative CPU estimate
            estimated_time = len(text) / estimated_chars_per_sec
            logger.info(f"Estimated generation time: ~{estimated_time/60:.1f} minutes (rough estimate)")

            # XTTS v2 parameters
            kwargs = {
                "text": text,
                "file_path": str(output_path),
                "language": language,  # Always English
            }

            # XTTS v2 requires speaker_wav - must provide reference audio
            if speaker:
                kwargs["speaker_wav"] = speaker  # Path to reference audio file
            else:
                raise ValueError(
                    "XTTS v2 requires a speaker_wav parameter (reference audio file) for voice cloning. "
                    "Please provide a reference audio file."
                )
            
            # XTTS v2 supports speed parameter
            if speed != 1.0:
                kwargs["speed"] = speed

            # Track progress for long texts
            start_time = time.time()
            
            # Try synthesis - if MPS fails, retry with CPU
            try:
                self._tts.tts_to_file(**kwargs)
            except Exception as synthesis_error:
                error_msg = str(synthesis_error)
                # Check for MPS channel limit error - retry with CPU
                if (self._device and "mps" in self._device.lower() and 
                    ("65536" in error_msg or "channels" in error_msg.lower() or "MPS" in error_msg)):
                    logger.warning(
                        f"MPS synthesis error: {error_msg}. "
                        "Retrying with CPU (MPS has channel limitations)."
                    )
                    # Move to CPU and retry
                    try:
                        self._tts.to("cpu")
                        self._device = "cpu"
                        logger.info("Moved TTS model to CPU for retry")
                        # Retry synthesis on CPU
                        self._tts.tts_to_file(**kwargs)
                        logger.info("✅ Synthesis succeeded on CPU after MPS failure")
                    except Exception as cpu_error:
                        logger.error(f"CPU retry also failed: {cpu_error}")
                        raise synthesis_error  # Raise original error
                else:
                    # Not an MPS error, or CPU retry failed - raise original error
                    raise
            
            elapsed = time.time() - start_time
            logger.info(f"Generation completed in {elapsed/60:.2f} minutes ({len(text)/elapsed:.1f} chars/sec)")

            # Add trailing silence to fix "s" sound cutoff issue (XTTS v2 limitation)
            self._add_trailing_silence(output_path)
            
            logger.info(f"✅ Audio generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to synthesize audio: {e}")
            raise

    def _add_trailing_silence(self, audio_path: Path, silence_duration_ms: int = 100) -> None:
        """
        Add trailing silence to audio file to fix XTTS v2 "s" sound cutoff issue.
        
        XTTS v2 has a known issue where fricative sounds (like "s") at the end
        of sentences can be cut off prematurely. Adding a small amount of trailing
        silence gives the audio more "room" and helps prevent cutoff artifacts.
        
        Args:
            audio_path: Path to WAV audio file
            silence_duration_ms: Duration of silence to add in milliseconds (default: 100ms)
        """
        try:
            with wave.open(str(audio_path), 'rb') as wav_file:
                params = wav_file.getparams()
                n_channels, sampwidth, framerate, n_frames, comptype, compname = params
                
                # Read all frames
                frames = wav_file.readframes(n_frames)
                
                # Calculate number of silence frames to add
                silence_frames = int(framerate * silence_duration_ms / 1000)
                
                # Create silence (zeros) with same sample width and channels
                if sampwidth == 1:
                    silence = array.array('B', [128] * silence_frames * n_channels)  # 128 = silence for 8-bit
                elif sampwidth == 2:
                    silence = array.array('h', [0] * silence_frames * n_channels)  # 0 = silence for 16-bit
                elif sampwidth == 4:
                    silence = array.array('i', [0] * silence_frames * n_channels)  # 0 = silence for 32-bit
                else:
                    logger.warning(f"Unsupported sample width: {sampwidth}, skipping trailing silence")
                    return
                
                # Append silence to frames
                if sampwidth == 1:
                    extended_frames = frames + silence.tobytes()
                else:
                    extended_frames = frames + silence.tobytes()
            
            # Write extended audio back to file
            with wave.open(str(audio_path), 'wb') as out_wav:
                out_wav.setparams(params)
                out_wav.writeframes(extended_frames)
            
            logger.debug(f"Added {silence_duration_ms}ms trailing silence to {audio_path.name}")
            
        except Exception as e:
            # Don't fail synthesis if trailing silence addition fails
            logger.warning(f"Failed to add trailing silence to {audio_path}: {e}")
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


# Singleton instance to prevent multiple model loads
_tts_engine_instance: Optional[TTSEngine] = None

def get_tts_engine(model_name: Optional[str] = None) -> TTSEngine:
    """
    Get TTS engine instance (singleton per model).
    
    Args:
        model_name: Optional model name (defaults to 'default')
        
    Returns:
        TTSEngine instance (reused across calls for same model)
    """
    global _tts_engine_instance
    model_name = model_name or "default"
    
    # Create new instance if needed or if model changed
    if _tts_engine_instance is None or _tts_engine_instance.model_name != model_name:
        _tts_engine_instance = TTSEngine(model_name=model_name)
        logger.info(f"Created new TTS engine instance for model: {model_name}")
    return _tts_engine_instance
