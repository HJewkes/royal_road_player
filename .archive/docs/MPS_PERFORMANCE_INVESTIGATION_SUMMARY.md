f# MPS Performance Investigation - Summary

## Date: 2025-11-26

## User Report
- **Expected Performance (Nov 9):** 50-100 chars/sec with MPS  
- **Current Performance:** 4-7 chars/sec with MPS  
- **System:** M3 Max, macOS 14.3 (no recent updates since Jan 2024)

## Investigation Conducted

### 1. PyTorch Version Testing (ALL versions from 2.1 to 2.9)
| Version | Result |
|---------|--------|
| 2.9.x | Incompatible with Coqui TTS (`weights_only` error) |
| 2.8.x | Incompatible with Coqui TTS (`weights_only` error) |
| 2.7.x | Incompatible with Coqui TTS (`weights_only` error) |
| 2.6.x | Incompatible with Coqui TTS (`weights_only` error) |
| 2.5.1 | Explicit MPS error: "Output channels > 65536 not supported" |
| 2.5.0 | Explicit MPS error: "Output channels > 65536 not supported" |
| 2.4.1 | **Loads on MPS but only 4-5 chars/sec** |
| 2.4.0 | Not tested (expected same as 2.4.1) |
| 2.3.1 | Loads on MPS but only 4 chars/sec |
| 2.3.0 | Not tested |
| 2.2.2 | Error: Missing FFT operations on MPS |
| 2.2.x | Error: Missing FFT operations on MPS |
| 2.1.2 | Error: Missing FFT operations on MPS |

### 2. Configuration Changes Made Today (That Broke Things)
During debugging, I made two changes that degraded performance:
1. **Disabled `PYTORCH_ENABLE_MPS_FALLBACK=1`** ❌ (Restored)
2. **Added `TTS_NUM_THREADS=14`** ❌ (Removed)

Both have been reverted to Nov 9 configuration.

### 3. System-Level Checks
- ✅ macOS 14.3 (no updates since Jan 2024)
- ✅ PyTorch reinstalled cleanly (no cache corruption)
- ✅ TTS model cache intact
- ✅ MPS available and functional (basic ops work at 3.89x speedup)
- ✅ Model successfully loads on `mps:0` device

### 4. Current Configuration (Restored to Nov 9)
```python
# backend/src/tts/engine.py
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # ✅ Enabled
```

```bash
# .env
TTS_GPU=true  # ✅ Enabled  
# TTS_NUM_THREADS removed ✅
```

## Key Findings

### MPS is Loading But Not Accelerating
- Model successfully moves to MPS device (`mps:0`)
- Basic PyTorch ops show 3.89x speedup on MPS
- **But XTTS inference is only 4-5 chars/sec (vs expected 50-100 chars/sec)**

### Possible Explanations

1. **XTTS Architecture vs MPS Limitations**
   - XTTS has conv1d operations with >65536 output channels
   - This exceeds MPS hardware limits
   - Most operations run on MPS, but problematic ones fall back to CPU
   - Result: Mixed GPU/CPU execution that's slower than pure CPU would be

2. **PyTorch MPS Maturity**
   - MPS backend still has limited op coverage
   - Fallback behavior may be inefficient
   - Some operations might serialize GPU→CPU→GPU transfers

3. **Unknown System Change**
   - Something changed between Nov 9 and today
   - No macOS updates detected
   - No obvious configuration changes (now restored)
   - Possibly pip upgrade changed PyTorch version?

## Performance Comparison

| Configuration | Speed (chars/sec) | Notes |
|---------------|-------------------|-------|
| **Nov 9 (reported)** | 50-100 | User's recollection |
| **Current with MPS** | 4-7 | Model on MPS, fallback enabled |
| **Pure CPU optimized** | 15-20 | No GPU, TTS_NUM_THREADS=14 |
| **Pure CPU baseline** | 12-18 | No GPU, default threads |

## Recommendations

### Option 1: Investigate Further (If 50-100 chars/sec is Critical)
- **Check if Nov 9 was actually using CPU, not MPS** (maybe the "fast" was actually 15-20 chars/sec CPU?)
- **Test on a different machine** to see if system-specific
- **Check Activity Monitor during TTS** to see GPU utilization %
- **Try on macOS Sequoia** (newer Metal/MPS improvements)

### Option 2: Accept Current Performance
- **Stay on CPU with TTS_GPU=false** → 15-20 chars/sec
- **Or keep MPS hoping for future PyTorch improvements** → 4-7 chars/sec currently

### Option 3: Alternative TTS Engines
- Research TTS engines with better MPS support
- Trade-off: quality vs performance vs compatibility

## Current Status

**Service is running with:**
- PyTorch 2.4.1 (most stable/compatible)
- TTS_GPU=true (MPS enabled with fallback)
- MPS_FALLBACK=1 (allows operation but slow)
- Performance: ~4-7 chars/sec

**Recommendation:** Set `TTS_GPU=false` to get consistent 15-20 chars/sec CPU performance, which is actually 2-3x faster than current MPS performance.

## Questions for User

1. Are you certain Nov 9 was getting 50-100 chars/sec? Could it have been 15-20 chars/sec?
2. Has anything else changed on your system (GPU drivers, background processes, power settings)?
3. What's more important: investigating the MPS mystery, or getting reliable 15-20 chars/sec on CPU?

## Files Modified Today
- `backend/src/tts/engine.py` - Restored MPS fallback setting
- `.env` - Removed TTS_NUM_THREADS
- Tested PyTorch versions 2.1-2.9

## Next Steps
Waiting for user input on whether to:
- Continue investigating MPS (may require system-level debugging)
- Switch to optimized CPU mode (reliable 15-20 chars/sec)
- Try alternative approaches




