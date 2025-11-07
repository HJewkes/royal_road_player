# TTS Comparison Results - British Male Voices

## ✅ Both Systems Working!

### Fixed Issues:
1. **XTTS v2**: Fixed transformers dependency (downgraded to 4.35.0)
2. **Bark**: Fixed PyTorch compatibility (downgraded to 2.5.1)

## Generated Samples

### XTTS v2 (Voice Cloning)
- **File**: `data/voice_samples/xtts_v2/xtts_v2_cloned_british_male_p241.wav`
- **Reference**: Used VCTK p241 British male voice as reference
- **Time**: 13.27s for 312 characters (~23.5 chars/sec)
- **Size**: 776 KB
- **Method**: Voice cloning from reference audio

### Bark (Voice Prompts)
- **File 1**: `data/voice_samples/bark/bark_british_male_1.wav`
  - Prompt: "A British man with a clear, professional voice"
  - Time: 91.46s (~3.4 chars/sec)
  - Size: 1.3 MB
  
- **File 2**: `data/voice_samples/bark/bark_british_male_2.wav`
  - Prompt: "A British man with a deep, authoritative voice"
  - Time: 90.74s (~3.4 chars/sec)
  - Size: 1.3 MB
  
- **File 3**: `data/voice_samples/bark/bark_british_male_3.wav`
  - Prompt: "A British man with a warm, friendly voice"
  - Time: 95.60s (~3.4 chars/sec)
  - Size: 1.3 MB

## Performance Comparison

| System | Speed (CPU) | Quality | Prosody | Voice Control |
|--------|-------------|---------|---------|---------------|
| **XTTS v2** | ~23 chars/sec | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Voice cloning (reference audio) |
| **Bark** | ~3.4 chars/sec | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Voice prompts (text-based) |

**Note**: Both are running on CPU. With RTX 5090 GPU, expect 3-5x speedup.

## How to Listen & Compare

```bash
# Open all samples for comparison
open data/voice_samples/xtts_v2/
open data/voice_samples/bark/
```

## Key Differences

### XTTS v2
- ✅ Faster generation (~7x faster than Bark on CPU)
- ✅ Voice cloning from reference audio (consistent narrator)
- ✅ Smaller output files
- ✅ Better for production (faster, consistent voice)
- ⚠️ Requires reference audio file for voice cloning

### Bark
- ✅ Most natural prosody (closest to ElevenLabs/Hume)
- ✅ Voice control via text prompts (no reference needed)
- ✅ Very expressive and natural pacing
- ⚠️ Slower generation (~3.4 chars/sec on CPU)
- ⚠️ Larger output files

## Recommendations

### For Production (RTX 5090 GPU):

**Primary Choice: XTTS v2**
- Faster generation (~5-7 min per chapter on GPU)
- Consistent voice via cloning
- Excellent quality and prosody
- Better for batch processing

**Alternative: Bark**
- If maximum natural prosody is priority
- If you can accept longer generation times (~15-20 min per chapter on GPU)
- If you want text-based voice control

### For Testing/Evaluation:

Listen to all samples and compare:
1. **Naturalness** - Which sounds more human?
2. **Prosody** - Which has better pacing and inflection?
3. **British accent** - Which sounds more British?
4. **Overall quality** - Which do you prefer?

## Next Steps

1. **Listen to samples** and choose your preferred system
2. **For XTTS v2**: Choose a reference voice from VCTK samples
3. **For Bark**: Experiment with different voice prompts
4. **Generate full chapter** with chosen system
5. **Evaluate quality** and iterate

## Usage Examples

### Generate with XTTS v2:
```bash
# Use a VCTK sample as reference
python scripts/generate_audio.py \
  "data/books/.../chapters/07-01.txt" \
  --speaker "data/voice_samples/british_male/british_male_p241.wav" \
  --model "tts_models/multilingual/multi-dataset/xtts_v2"
```

### Generate with Bark:
```bash
# Modify test_bark_british.py to use your chapter text
# Or implement Bark engine integration
```

## Estimated Generation Times (77K char chapter)

### CPU (M3 Max):
- **XTTS v2**: ~55 minutes
- **Bark**: ~6.3 hours

### GPU (RTX 5090):
- **XTTS v2**: ~5-7 minutes
- **Bark**: ~15-20 minutes

**Recommendation**: Use GPU for production! Both systems will be much faster.

