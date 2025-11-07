# Testing XTTS v2 and Bark - British Male Voices

## Current Status

### XTTS v2
- ✅ Model downloaded (1.87GB)
- ⚠️ Transformers dependency issue (fixing)
- ✅ License accepted
- Ready to test once dependency is fixed

### Bark
- ✅ Installed
- ⚠️ PyTorch 2.6 compatibility issue
- Needs PyTorch < 2.6 or fix

## Quick Fixes

### Fix XTTS v2 Transformers Issue

```bash
source venv/bin/activate
pip install --upgrade transformers
# Or specific version:
pip install transformers>=4.35.0
```

### Fix Bark PyTorch Issue

**Option 1: Downgrade PyTorch (Recommended)**
```bash
source venv/bin/activate
pip install "torch<2.6" "torchaudio<2.6"
```

**Option 2: Use patched script**
The `test_bark_british.py` script includes a patch, but may need more work.

## Testing Instructions

### Test XTTS v2

```bash
source venv/bin/activate
python scripts/test_xtts_v2_british.py
```

When prompted for license, type `y` and press Enter.

### Test Bark

After fixing PyTorch:
```bash
source venv/bin/activate
python scripts/test_bark_british.py
```

## Expected Outputs

- **XTTS v2**: `data/voice_samples/xtts_v2/xtts_v2_british_default.wav`
- **Bark**: `data/voice_samples/bark/bark_british_male_*.wav` (multiple samples)

## Comparison

After generating samples, compare:
1. **Naturalness** - Which sounds more human?
2. **Prosody** - Which has better pacing and inflection?
3. **British accent** - Which sounds more British?
4. **Quality** - Overall audio quality

## Next Steps

1. Fix transformers dependency for XTTS v2
2. Fix PyTorch for Bark (or use XTTS v2)
3. Generate samples from both
4. Compare quality
5. Choose best for production

