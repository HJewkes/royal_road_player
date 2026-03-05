# MPS Performance Investigation

## Date: 2025-11-25

## Summary

Investigated why MPS (Apple Silicon GPU) is not providing expected speed improvements for XTTS v2 TTS generation.

## Timeline

### Initial State
- TTS_GPU=true set in .env
- PyTorch 2.5.1 installed
- Performance: ~18 chars/sec (expected 200-500 chars/sec with MPS)
- Memory usage: 6680 MB

### Step 1: PyTorch Downgrade to 2.4.1
- Downgraded from PyTorch 2.5.1 to 2.4.1
- Rationale: Known MPS performance regression in 2.5.1 (60% slowdown reported)
- Result: Performance unchanged (~12-18 chars/sec)
- Memory usage: Dropped to 1269 MB (indication model might not be fully loading)

### Step 2: MPS Functionality Test
```bash
# Basic PyTorch MPS test
MPS available: True
MPS built: True
CPU matmul time: 0.1764s
MPS matmul time: 0.0454s
MPS speedup: 3.89x
```
✅ MPS is functional for basic PyTorch operations

### Step 3: XTTS + MPS Direct Test
```python
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
tts.to('mps')
```

**ERROR DISCOVERED:**
```
RuntimeError: Boolean value of Tensor with more than one value is ambiguous
```

This error occurs when trying to move XTTS model to MPS device!

## Root Cause

**XTTS v2 has a fundamental incompatibility with MPS** that causes a RuntimeError when attempting to use the MPS backend. This is NOT a PyTorch version issue - it's an XTTS + MPS compatibility issue.

The error "Boolean value of Tensor with more than one value is ambiguous" typically occurs when:
1. Code tries to use a tensor in a boolean context (if/while)
2. The tensor has multiple values (not a scalar)
3. This is hitting MPS-specific code paths that don't exist in CPU/CUDA

## Why Performance Was Slow

The model was **silently falling back to CPU** despite appearing to load on MPS:
1. `tts.to('mps')` appeared to succeed
2. But actual inference operations hit the RuntimeError
3. With `PYTORCH_ENABLE_MPS_FALLBACK=1` (previously set), operations fell back to CPU
4. Without the fallback, operations fail with RuntimeError
5. This explains the ~18 chars/sec (CPU speed) vs expected 200-500 chars/sec (GPU speed)

## Why Memory Usage Dropped

The memory drop from 6680 MB → 1269 MB suggests:
- Model not fully loading to MPS
- Less memory needed when failing/falling back to CPU
- GPU memory not being allocated

## Next Steps

### Option 1: Stay on CPU (Current State)
- Accept CPU performance (~15-20 chars/sec)
- Optimize CPU threading (already done: TTS_NUM_THREADS=14)
- Pros: Stable, works
- Cons: 10-25x slower than GPU could be

### Option 2: Research XTTS MPS Fixes
- Search for XTTS patches/forks that fix MPS compatibility
- Look for specific code changes in XTTS that cause the boolean tensor issue
- May require modifying XTTS source code
- Uncertain timeline/success rate

### Option 3: Try CUDA (If Hardware Available)
- XTTS works well with CUDA
- Would need NVIDIA GPU
- Not applicable for current Apple Silicon hardware

### Option 4: Alternative TTS Engines
- Look for TTS engines with better MPS support
- Evaluate quality/speed tradeoffs
- Would require significant refactoring

### Option 5: Try PyTorch 2.5.0 (Not 2.5.1)
- 2.5.1 had MPS regressions, but 2.5.0 might work
- Worth testing before giving up on MPS
- Could combine with XTTS source code investigation

## Recommendation

1. **Immediate**: Test PyTorch 2.5.0 to see if it avoids both the 2.5.1 regression AND the XTTS boolean tensor issue
2. **Short-term**: Search for XTTS MPS compatibility patches/issues on GitHub
3. **Long-term**: If no fix exists, either accept CPU performance or evaluate alternative TTS engines

## Key Findings

- ✅ MPS hardware acceleration works (3.89x speedup on basic ops)
- ❌ XTTS v2 has incompatibility with MPS (boolean tensor error)
- ⚠️ Silent fallback to CPU was masking the actual error
- 📊 Current performance (18 chars/sec) is pure CPU, not MPS

## References

- PyTorch MPS Issue: https://github.com/pytorch/pytorch/issues/139389
- XTTS v2 Model: tts_models/multilingual/multi-dataset/xtts_v2
- Error Type: RuntimeError during boolean tensor evaluation in MPS operations




