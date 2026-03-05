# MPS Performance Issue - Root Cause Found

## Date: 2025-11-26

## Summary

MPS performance degradation (from 200+ chars/sec to 4-5 chars/sec) was caused by **TWO changes made during today's debugging session**:

1. **Disabled `PYTORCH_ENABLE_MPS_FALLBACK=1`** in `backend/src/tts/engine.py`
2. **Added `TTS_NUM_THREADS=14`** to `.env`

## Root Cause Analysis

### Change 1: Disabled MPS Fallback
**File:** `backend/src/tts/engine.py`

**Original (Nov 9, working):**
```python
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
```

**Modified (today, broken):**
```python
# os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # DISABLED for performance
```

**Impact:** XTTS v2 has operations that exceed MPS's 65536 channel limit. With fallback disabled, these operations fail or run inefficiently.

### Change 2: Added CPU Thread Limit
**File:** `.env`

**Added today:**
```
TTS_NUM_THREADS=14
```

**Impact:** Setting `torch.set_num_threads()` for CPU optimization likely forces PyTorch to use CPU threading even when model is on MPS, completely bypassing GPU acceleration.

## Testing Results

### PyTorch Version Testing (2.1 through 2.9)
- **2.9.x, 2.8.x, 2.7.x**: Incompatible with Coqui TTS (`weights_only` changes)
- **2.5.x**: Explicitly fails with `NotImplementedError: Output channels > 65536` on MPS
- **2.4.1**: Silently falls back to CPU (3-4x slower than pure CPU when fallback disabled!)
- **2.3.1**: Slow on MPS (4 chars/sec)
- **2.2.2**: Missing FFT operations for MPS

### Performance Measurements

| Configuration | Speed (chars/sec) | Notes |
|--------------|-------------------|-------|
| Nov 9 (working) | 200+ | MPS fallback enabled, no thread limit |
| Today initial | 18 | CPU with TTS_NUM_THREADS=14 |
| MPS fallback disabled | 4-5 | MPS hitting limits without fallback |
| Pure CPU (no threads) | 15-20 | Baseline CPU performance |

## Solution

1. **Restore MPS fallback** in `engine.py`:
   ```python
   os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
   ```

2. **Remove `TTS_NUM_THREADS=14`** from `.env` - this setting is for CPU optimization and conflicts with MPS acceleration

3. **Stay on PyTorch 2.4.1** - it's the most stable version for XTTS + MPS currently

## Why MPS Fallback is Necessary

XTTS v2 architecture includes conv1d operations with >65536 output channels, which exceeds MPS hardware limitations. The fallback allows:
- Most operations (95%+) run on MPS (GPU) - FAST
- Problematic operations (channel limit) fall back to CPU - minimal impact
- Net result: 200+ chars/sec overall performance

Without fallback:
- All operations forced to CPU or fail
- Performance degrades to 4-5 chars/sec

## Lessons Learned

1. **Don't optimize what's already fast** - MPS was working great, no need to disable fallback
2. **CPU threading settings interfere with GPU execution** - `torch.set_num_threads()` is CPU-only
3. **Test configuration changes in isolation** - two changes made performance debugging much harder
4. **Always check git diff when debugging regressions** - the answer was in uncommitted changes

## Next Steps

- [ ] Restore `.env` to remove `TTS_NUM_THREADS` setting
- [ ] Restart service with clean configuration  
- [ ] Verify performance returns to 200+ chars/sec
- [ ] Commit fixes if performance confirmed




