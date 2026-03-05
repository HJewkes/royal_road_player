# TTS Performance Analysis

**Date:** 2025-11-25  
**Issue:** Very slow processing times (9 chars/sec vs expected 50-500 chars/sec)  
**Status:** 🔴 **CRITICAL PERFORMANCE ISSUE**

---

## Summary

The TTS audio generation is running **5-50x slower than expected**:
- **Current:** ~9 chars/sec (~20 seconds per chunk)
- **Expected CPU:** ~50-100 chars/sec (~2-4 seconds per chunk)
- **Expected MPS:** ~200-500 chars/sec (~0.5-1 second per chunk)

---

## Performance Statistics

### Overall Stats (2,119 completed chunks)

| Metric | Value |
|--------|-------|
| **Average time per chunk** | 19.7 seconds |
| **Average chunk size** | 185 characters |
| **Chars/sec** | **9.1 chars/sec** 🔴 |
| **Slowest chunk** | **1,916 seconds (32 minutes!)** |
| **Fastest chunk** | 1.0 seconds |

### Performance by Chapter

| Chapter | Avg Time (sec) | Avg Chars | Chars/Sec | Status |
|---------|----------------|-----------|-----------|--------|
| 1 | 12.0 | 188 | 15.7 | 🟡 Slow |
| 2 | 9.7 | 182 | 18.8 | 🟡 Slow |
| 3 | 10.5 | 185 | 17.6 | 🟡 Slow |
| 4 | 21.7 | 187 | **8.6** | 🔴 Very Slow |
| 5 | 31.3 | 180 | **5.8** | 🔴 Very Slow |
| 6 | 11.7 | 185 | 15.8 | 🟡 Slow |
| 7 | 45.2 | 184 | **4.1** | 🔴 Extremely Slow |

**⚠️ Processing is getting SLOWER over time!**

### Worst Performing Chunks

| Chapter | Time (sec) | Size (chars) | Chars/Sec |
|---------|-----------|--------------|-----------|
| 5 | 1,916 | 246 | **0.13** 🔴 |
| 4 | 1,895 | 110 | **0.06** 🔴 |
| 5 | 1,065 | 190 | **0.18** 🔴 |
| 5 | 938 | 196 | **0.21** 🔴 |
| 4 | 764 | 224 | **0.29** 🔴 |

**Some chunks are taking 15-30 MINUTES for ~200 characters!**

---

## System Configuration

### Current Settings

```
TTS_GPU=true               ✅ Enabled
TTS_NUM_THREADS=None      ⚠️  Not set (should be 14)
TTS Model: XTTS v2        ✅ Correct
```

### Hardware

- **CPU:** 14 cores (physical)
- **GPU:** Apple Silicon MPS available ✅
- **PyTorch:** 2.5.1 with MPS support ✅

### Expected vs Actual

| Mode | Expected | Actual | Status |
|------|----------|--------|--------|
| CPU | 50-100 chars/sec | **9 chars/sec** | 🔴 5-10x slower |
| MPS | 200-500 chars/sec | **9 chars/sec** | 🔴 20-50x slower |

---

## Root Cause Analysis

### Hypothesis 1: MPS Failing Silently ⭐ MOST LIKELY

**Evidence:**
- TTS_GPU=true but performance matches neither CPU nor MPS
- No MPS initialization logs in `queue_processor.log`
- Performance degrading over time (thermal throttling?)
- Some chunks taking 30+ minutes (suggests fallback or retry loops)

**MPS Known Issues:**
- Channel limit errors (> 65536 channels)
- Memory leaks causing gradual slowdown
- Thermal throttling on sustained workloads
- Fall back to CPU with no clear error message

**Check:**
```python
# In engine.py lines 86-93, there's MPS error handling
# But errors might not be logging to queue_processor.log
```

### Hypothesis 2: Model Reloading Per Chunk

**Evidence:**
- Singleton pattern should prevent this
- But performance degradation suggests possible memory issues

**Check:**
- Look for "Loading XTTS v2 model" messages repeated in logs
- Check memory usage over time

### Hypothesis 3: Thread/CPU Constraints

**Evidence:**
- TTS_NUM_THREADS=None (not set)
- 14 physical cores available but not explicitly configured

**Impact:**
- PyTorch might be using only 1 thread
- Could explain 5-10x slowdown on CPU

### Hypothesis 4: I/O Bottleneck

**Evidence:**
- Speaker WAV file loaded for each chunk
- Previous errors about "failed to open file"

**Less Likely:** I/O should be fast, not 30+ minutes

---

## Detailed Investigation Needed

### Missing Logs

The TTS engine logs device selection on load:
```python
logger.info("✅ Apple Silicon MPS detected - using GPU acceleration")
logger.info(f"✅ Moved TTS model to {device.upper()} device")
```

**But these logs are NOT in `queue_processor.log`!**

This means either:
1. Model loaded before background processor started (logs went elsewhere)
2. Model never loaded successfully (would crash on first synthesis)
3. Logs going to different handler

**Need to check:** Where do TTS initialization logs go?

### MPS Fallback Detection

The code has MPS error handling (engine.py:86-93):
```python
if "mps" in device.lower() and ("65536" in error_msg or "channels" in error_msg.lower()):
    logger.warning("MPS device error detected... Falling back to CPU.")
```

**But no such warnings in logs!**

This suggests either:
1. MPS is working (but very slow - unlikely)
2. MPS failed silently during model load
3. Model never attempted MPS

---

## Immediate Fixes

### Fix 1: Set CPU Threads (Quick Win)

Add to `.env`:
```bash
TTS_NUM_THREADS=14
```

**Expected improvement:** If on CPU, could get 2-5x speedup (up to 20-50 chars/sec)

### Fix 2: Add Comprehensive Logging

Modify `backend/src/tts/engine.py` to log device info to file AND console:

```python
def load_model(self):
    # ... existing code ...
    
    # Log to BOTH file and console
    print(f"🎤 TTS: Attempting to use device: {device}")
    logger.info(f"TTS: Attempting to use device: {device}")
    
    self._tts.to(device)
    
    # Verify actual device after loading
    if hasattr(self._tts, 'synthesizer'):
        model = self._tts.synthesizer.tts_model
        first_param = next(model.parameters(), None)
        if first_param:
            actual_device = first_param.device
            print(f"🎤 TTS: Model actually on device: {actual_device}")
            logger.info(f"TTS: Model actually on device: {actual_device}")
```

### Fix 3: Force CPU Mode for Testing

To rule out MPS issues, temporarily set:
```bash
TTS_GPU=false
TTS_NUM_THREADS=14
```

**Expected:** 50-100 chars/sec (still 5-10x better than current)

### Fix 4: Monitor for Memory Leaks

Add memory monitoring:
```python
import psutil
process = psutil.Process()
mem_mb = process.memory_info().rss / 1024 / 1024
logger.info(f"Memory usage: {mem_mb:.1f} MB")
```

Log this every 10 chunks to detect leaks.

---

## Recommended Action Plan

### Phase 1: Immediate Diagnostics (5 minutes)

1. **Set TTS_NUM_THREADS=14** in `.env`
2. **Restart server** and monitor next 5-10 chunks
3. **Check if performance improves** (should see 2-5x if on CPU)

### Phase 2: Enhanced Logging (15 minutes)

1. **Add device verification logging** to `engine.py`
2. **Add console output** for TTS device selection
3. **Restart and watch logs** during model load
4. **Verify which device is actually being used**

### Phase 3: Test CPU-Only Mode (30 minutes)

1. **Set TTS_GPU=false, TTS_NUM_THREADS=14**
2. **Restart and process 20 chunks**
3. **Compare performance:**
   - If much faster → MPS was the problem
   - If same speed → Different bottleneck

### Phase 4: MPS Investigation (if Phase 3 shows MPS issue)

1. **Review PyTorch MPS known issues**
2. **Test with smaller chunks** (< 100 chars)
3. **Monitor thermal throttling** (check CPU temperature)
4. **Try different PyTorch version** if needed

---

## Expected Outcomes

### If CPU Thread Issue (BEST CASE)

- Set TTS_NUM_THREADS=14
- **Expected:** 20-50 chars/sec (2-5x improvement)
- **Time per chunk:** 4-10 seconds (vs 20 currently)
- **Total time for 3,810 pending:** ~4-10 hours (vs 21 hours currently)

### If MPS Issue (LIKELY)

- Disable MPS, use CPU with threads
- **Expected:** 50-100 chars/sec (5-10x improvement)
- **Time per chunk:** 2-4 seconds
- **Total time for 3,810 pending:** ~2-4 hours

### If Unknown Bottleneck (WORST CASE)

- Need deeper investigation
- Profile with cProfile or py-spy
- Check I/O, network, speaker WAV loading
- May need code changes

---

## Current Impact

With 3,810 chunks remaining at current rate:
- **Current rate:** 9 chars/sec (~20 sec/chunk)
- **Estimated time remaining:** ~21 hours
- **If we fix to 50 chars/sec:** ~4 hours ✅
- **If we fix to 200 chars/sec:** ~1 hour ✅✅

**The system is currently running at 5-50x slower than it should be!**

---

## Next Steps

**IMMEDIATE (do now):**
1. Add `TTS_NUM_THREADS=14` to `.env`
2. Restart server
3. Monitor next 10 chunks for improvement

**SHORT TERM (within 1 hour):**
1. Add enhanced device logging
2. Verify actual device being used
3. Test CPU-only mode if needed

**FOLLOW UP:**
1. Document final solution
2. Add monitoring/alerting for slow chunks
3. Consider chunk size optimization
4. Profile if issue persists

---

## Monitoring Commands

```bash
# Watch recent processing times
watch -n 5 'tail -5 /Users/hjewkes/Documents/projects/audiobook/logs/queue_processor.log | grep "✅ Processed"'

# Check current rate
curl -s http://localhost:8000/api/queue/status

# Check device configuration
python scripts/check_tts_device.py

# Monitor system resources
top -pid $(pgrep -f "uvicorn.*app:app" | head -1)
```

---

## Conclusion

The TTS system is running **5-50x slower than expected**, with some chunks taking over 30 minutes. The most likely causes are:

1. **MPS (Apple Silicon GPU) failing silently** and falling back to unoptimized CPU
2. **CPU threads not configured** (missing TTS_NUM_THREADS)
3. **Possible memory leak** causing degradation over time

**Immediate action:** Set TTS_NUM_THREADS=14 and restart. This alone could provide 2-5x improvement.

**Critical:** Need to add device verification logging to confirm which device is actually being used (CPU vs MPS).




