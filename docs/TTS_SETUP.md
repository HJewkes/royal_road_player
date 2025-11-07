# TTS Setup Guide

## Python Version Requirements

**Important:** Coqui TTS requires Python <3.12. If you're using Python 3.12 or newer, you have two options:

1. **Use Python 3.11** (Recommended for best TTS quality)
   ```bash
   # Install Python 3.11 using pyenv or your system package manager
   pyenv install 3.11.9
   pyenv local 3.11.9
   
   # Then recreate venv
   make teardown
   make setup
   ```

2. **Use Piper TTS** (Lighter weight, works with newer Python)
   - Update `.env`: `TTS_ENGINE=piper`
   - Note: Piper TTS implementation is pending

## Coqui TTS Setup

### Automatic Setup

```bash
# Check and download TTS models
make setup-tts-model
```

### Manual Setup

1. **Install TTS library** (if not already installed):
   ```bash
   make install-tts
   ```

2. **Verify installation**:
   ```bash
   source venv/bin/activate
   python scripts/setup_tts.py
   ```

## Model Selection

The default model is **XTTS v2** (`tts_models/multilingual/multi-dataset/xtts_v2`), which provides:
- ✅ Highest quality, most natural speech
- ✅ Multilingual support
- ✅ Voice cloning capabilities
- ✅ Emotion control
- ✅ Speed control
- ✅ SSML support (future)

### Alternative Models

You can change the model in `.env`:

```bash
# XTTS v2 (default - best quality)
TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2

# FastTTS (faster, lower quality)
TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC

# Other options available via Coqui TTS model list
```

## Generating Audio

### Basic Usage

Audio generation is primarily handled through the web interface. You can also use the Python API directly:

```python
from src.tts.generator import AudioGenerator
from pathlib import Path

generator = AudioGenerator()

# Generate chunked audio (recommended for long chapters)
audio_files = generator.generate_chapter_chunked(
    text_path=Path("data/books/.../chapters/07-01 - Chapter Title.txt"),
    chunk_duration_minutes=1.0
)

# Generate single audio file
audio_path = generator.generate_chapter(
    text_path=Path("chapter.txt"),
    output_path=Path("output.wav")
)
```

### Advanced Options

```python
from src.tts.generator import AudioGenerator
from pathlib import Path

generator = AudioGenerator()

# With speaker reference (voice cloning)
audio_files = generator.generate_chapter_chunked(
    text_path=Path("chapter.txt"),
    speaker="path/to/reference_voice.wav",
    chunk_duration_minutes=1.0
)

# With speed adjustment
audio_files = generator.generate_chapter_chunked(
    text_path=Path("chapter.txt"),
    speed=1.2,
    chunk_duration_minutes=1.0
)

# With emotion
audio_files = generator.generate_chapter_chunked(
    text_path=Path("chapter.txt"),
    emotion="happy",
    chunk_duration_minutes=1.0
)

# With language
audio_files = generator.generate_chapter_chunked(
    text_path=Path("chapter.txt"),
    language="en",
    chunk_duration_minutes=1.0
)
```

## Configuration

Edit `.env` to set default TTS parameters:

```bash
TTS_ENGINE=coqui
TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
TTS_LANGUAGE=en
TTS_SPEED=1.0
TTS_EMOTION=neutral  # Optional: neutral, happy, sad, angry, etc.
TTS_SPEAKER=  # Optional: path to reference audio file
```

## Troubleshooting

### Model Download Issues

If model download fails:
1. Check internet connection
2. Ensure sufficient disk space (XTTS v2 is ~2GB)
3. Try manual download: The model will download automatically on first use

### Memory Issues

XTTS v2 requires significant RAM:
- Minimum: 4GB RAM
- Recommended: 8GB+ RAM
- GPU: Optional but significantly faster

### Audio Quality Issues

- Try adjusting `TTS_SPEED` (0.8-1.2 range often works best)
- Experiment with different emotions
- Use a speaker reference for consistent voice

## Next Steps

After generating your first audio file, you can:
1. Listen to the output and assess quality
2. Experiment with speed, emotion, and other parameters
3. Consider using LLM annotation (Phase 3) to improve text structure for better audio

