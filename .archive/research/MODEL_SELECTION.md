# TTS Model Selection Guide

## Current Model

**Currently using:** `tts_models/en/vctk/vits`

**Why this model:**
- ✅ High quality, natural-sounding speech
- ✅ Multiple speaker voices (109 speakers available)
- ✅ British English accents (VCTK dataset)
- ✅ Good balance of quality and speed
- ✅ No license restrictions
- ✅ Works well for audiobook narration

## Model Selection Criteria

When choosing a TTS model, consider:

### 1. **Quality vs Speed Trade-off**

| Model Type | Quality | Speed | Best For |
|------------|---------|-------|----------|
| **XTTS v2** | ⭐⭐⭐⭐⭐ | Medium | Best quality, voice cloning |
| **Tacotron2-DDC** | ⭐⭐⭐⭐ | Slow | High quality, single voice |
| **VITS (VCTK)** | ⭐⭐⭐⭐ | Fast | Quality + speed, multi-voice |
| **Glow-TTS** | ⭐⭐⭐ | Very Fast | Fast generation, good quality |
| **Speedy-Speech** | ⭐⭐⭐ | Fastest | Speed priority |

### 2. **Voice Options**

- **Single-speaker models**: One fixed voice (e.g., Tacotron2-DDC)
- **Multi-speaker models**: Multiple voices to choose from (e.g., VCTK/VITS)
- **Voice cloning**: Use your own voice sample (XTTS v2)

### 3. **Language Support**

- **English-only**: Most models (LJSpeech, VCTK)
- **Multilingual**: XTTS v2 (17 languages)

### 4. **License Requirements**

- **Open source**: Most models (VCTK, LJSpeech)
- **Commercial license**: XTTS v2 (requires acceptance)

## Available Models

### High-Quality Options

#### 1. **`tts_models/en/vctk/vits`** ⭐ CURRENT
- **Quality**: ⭐⭐⭐⭐ (Very Good)
- **Speed**: ~100-150 chars/sec (CPU)
- **Voices**: 109 speakers (British accents)
- **License**: Open source
- **Best for**: Audiobooks with voice variety

**Pros:**
- Multiple British voices
- Good quality/speed balance
- No license issues

**Cons:**
- Requires speaker selection
- Slightly slower than fastest models

#### 2. **`tts_models/multilingual/multi-dataset/xtts_v2`**
- **Quality**: ⭐⭐⭐⭐⭐ (Best)
- **Speed**: ~100-200 chars/sec (CPU)
- **Voices**: Voice cloning + default voices
- **License**: Requires acceptance (non-commercial CPML)
- **Best for**: Highest quality, voice cloning

**Pros:**
- Highest quality
- Voice cloning support
- Multilingual
- Emotion control

**Cons:**
- Requires license acceptance
- Slower than VITS
- Larger model size

#### 3. **`tts_models/en/ljspeech/tacotron2-DDC`**
- **Quality**: ⭐⭐⭐⭐ (Very Good)
- **Speed**: ~50-100 chars/sec (CPU, slower)
- **Voices**: Single speaker (American English)
- **License**: Open source
- **Best for**: High quality, single voice

**Pros:**
- Very high quality
- No speaker selection needed
- Open source

**Cons:**
- Single voice only
- Slower generation
- American accent (not British)

### Fast Options

#### 4. **`tts_models/en/ljspeech/glow-tts`**
- **Quality**: ⭐⭐⭐ (Good)
- **Speed**: ~150-200 chars/sec (CPU, faster)
- **Voices**: Single speaker
- **License**: Open source
- **Best for**: Fast generation, good quality

#### 5. **`tts_models/en/ljspeech/speedy-speech`**
- **Quality**: ⭐⭐⭐ (Good)
- **Speed**: ~200-300 chars/sec (CPU, fastest)
- **Voices**: Single speaker
- **License**: Open source
- **Best for**: Speed priority

## Model Comparison for Your Use Case

### For Audiobook Narration:

**Recommended: `tts_models/en/vctk/vits` (Current)**
- ✅ Multiple British voices (fits your content)
- ✅ Good quality for long-form content
- ✅ Reasonable generation speed
- ✅ No license restrictions

**Alternative: `tts_models/multilingual/multi-dataset/xtts_v2`**
- ✅ Highest quality
- ✅ Voice cloning (consistent narrator voice)
- ⚠️ Requires license acceptance
- ⚠️ Slower generation

### For Testing/Development:

**Recommended: `tts_models/en/ljspeech/glow-tts`**
- ✅ Fast generation
- ✅ Good enough quality for testing
- ✅ Simple (single voice)

## How to Change Models

### Option 1: Update `.env` file

```bash
# Edit .env
TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
```

### Option 2: Use CLI parameter (future feature)

```bash
python scripts/generate_audio.py chapter.txt --model tts_models/en/ljspeech/glow-tts
```

### Option 3: Test different models

```bash
# Test a model
python scripts/quick_test.py  # Uses current .env setting

# Or modify scripts/test_voices.py to test different models
```

## Performance Expectations

### Generation Time Estimates (77K character chapter):

| Model | CPU Time | GPU Time |
|-------|----------|----------|
| VITS (VCTK) | ~12-15 min | ~4-5 min |
| XTTS v2 | ~15-20 min | ~5-7 min |
| Tacotron2-DDC | ~20-25 min | ~7-10 min |
| Glow-TTS | ~8-10 min | ~3-4 min |
| Speedy-Speech | ~5-7 min | ~2-3 min |

**Note**: M3 Max has Neural Engine which may accelerate some operations, but actual GPU acceleration depends on PyTorch MPS support.

## Recommendations

### For Your Project (British Audiobook):

1. **Primary**: `tts_models/en/vctk/vits` (current)
   - Best fit for British content
   - Multiple voice options
   - Good quality/speed balance

2. **If quality is priority**: `tts_models/multilingual/multi-dataset/xtts_v2`
   - Accept license
   - Use voice cloning for consistent narrator
   - Slower but best quality

3. **If speed is priority**: `tts_models/en/ljspeech/glow-tts`
   - Faster generation
   - Single voice (American accent)
   - Good for testing

## Testing Models

To test different models:

```bash
# 1. Update .env with new model
echo "TTS_MODEL=tts_models/en/ljspeech/glow-tts" >> .env

# 2. Test with quick script
python scripts/quick_test.py

# 3. Compare quality and speed
# 4. Choose best for your needs
```

## Model Selection Checklist

- [ ] Quality requirements (high/medium/acceptable)
- [ ] Speed requirements (fast/medium/slow acceptable)
- [ ] Voice variety needed (single/multiple/cloning)
- [ ] Language/accent requirements (British/American/multilingual)
- [ ] License constraints (open source/commercial)
- [ ] Hardware (CPU/GPU available)

## Current Recommendation

**Stick with `tts_models/en/vctk/vits`** because:
1. ✅ Matches your British content perfectly
2. ✅ Multiple voice options (you've tested 20+ British male voices)
3. ✅ Good quality for audiobook narration
4. ✅ Reasonable generation speed (~12-15 min per chapter)
5. ✅ No license issues

Consider switching to XTTS v2 only if:
- You need voice cloning for consistent narrator
- Quality is more important than speed
- You're okay with license acceptance

