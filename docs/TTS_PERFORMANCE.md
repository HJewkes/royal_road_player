# TTS Performance Guide

## Generation Speed

Based on testing with `tts_models/en/vctk/vits`:

- **Short text (< 100 chars)**: ~0.3-0.5 seconds
- **CPU performance**: ~100-150 characters/second
- **GPU performance**: ~300-500 characters/second (if GPU available)

### Expected Generation Times

For a typical chapter (~77,000 characters):

- **CPU (M3 Max)**: ~12-15 minutes per chapter
- **GPU (if available)**: ~4-5 minutes per chapter

**Note**: First generation may be slower due to model initialization.

## Progress Tracking

The TTS engine now provides:
1. **Time estimate** before generation starts
2. **Real-time progress** (via Coqui's internal progress bars)
3. **Completion stats** (actual time, chars/sec)

Example output:
```
Text length: 77118 characters
Estimated generation time: ~12.9 minutes (rough estimate)
Generating audio...
[... progress bars ...]
Generation completed in 13.2 minutes (97.3 chars/sec)
```

## Chunking Long Texts

For very long chapters (>10,000 characters), consider chunking:

```python
from src.tts.chunker import chunk_text, should_chunk

if should_chunk(text):
    chunks = chunk_text(text, max_chunk_size=5000)
    # Generate each chunk separately, then concatenate
```

**Benefits of chunking:**
- Better progress visibility
- Can resume if interrupted
- Lower memory usage
- Can parallelize (future feature)

**Trade-offs:**
- Slight audio discontinuities at chunk boundaries
- More complex audio file management

## Available Models

### Current Model: `tts_models/en/vctk/vits`

**Pros:**
- High quality, natural-sounding speech
- Multiple speaker voices (100+ options)
- Good balance of quality and speed
- No license restrictions

**Cons:**
- Requires speaker selection (we auto-select first if not specified)
- Slightly slower than some alternatives

### Alternative Models

1. **`tts_models/en/ljspeech/tacotron2-DDC`**
   - Single speaker
   - Very high quality
   - Slower generation

2. **`tts_models/en/ljspeech/glow-tts`**
   - Single speaker
   - Fast generation
   - Good quality

3. **`tts_models/multilingual/multi-dataset/xtts_v2`** (requires license)
   - Best quality
   - Voice cloning support
   - Multilingual
   - Requires license acceptance

## Speaker Selection

The VCTK model has 100+ speakers. To test different voices:

```bash
# Generate with specific speaker
python scripts/generate_audio.py chapter.txt --speaker p225  # Female voice
python scripts/generate_audio.py chapter.txt --speaker p226  # Male voice
python scripts/generate_audio.py chapter.txt --speaker p227  # Another voice
```

Common speaker IDs:
- `p225`, `p226`, `p227`: Clear, neutral voices
- `p228`, `p229`, `p230`: Alternative voices
- See full list by running: `python -c "from TTS.api import TTS; tts = TTS('tts_models/en/vctk/vits'); print(tts.speakers[:20])"`

## Optimization Tips

1. **Use GPU if available**: 3-5x faster generation
2. **Batch processing**: Generate multiple chapters in sequence (model stays loaded)
3. **Chunk very long chapters**: Better progress tracking and memory usage
4. **Choose appropriate speaker**: Some voices may be clearer for audiobooks

## Monitoring Generation

The system logs:
- Model loading time
- Text length and estimated time
- Actual generation time
- Characters per second achieved
- File size

Check logs for detailed performance metrics.

