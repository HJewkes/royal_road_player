# Memory Leak Investigation Plan

**Date:** 2025-11-25  
**Issue:** Processing slowing down over time (Chapter 1: 15 chars/sec → Chapter 7: 4 chars/sec)  
**Status:** 🔍 **INVESTIGATING** - Monitoring enabled

---

## Applied Fixes

### 1. CPU Thread Optimization ✅
**File:** `.env`  
**Change:** Added `TTS_NUM_THREADS=14`

**Expected Impact:**  
- 2-5x speedup if on CPU
- Better utilization of 14-core CPU
- Reduced context switching

### 2. Enhanced Device Logging ✅
**File:** `backend/src/tts/engine.py`

**Changes:**
- Log device selection to both console and file
- Verify actual device after model load
- Print device info during initialization

**Purpose:** Confirm whether MPS or CPU is actually being used

### 3. Memory Leak Detection ✅  
**File:** `backend/src/services/job_queue.py`

**Changes:**
- Log memory usage every minute
- Track total chunks processed
- Use psutil to monitor RSS memory

**Output format:**
```
📊 Memory: 3745.8 MB | Chunks processed: 1
```

---

## Monitoring Plan

### Phase 1: Baseline Establishment (1 hour)

**Monitor:**
1. Processing speed (chars/sec) - should improve with TTS_NUM_THREADS
2. Memory usage over time - watch for growth
3. Device being used (MPS vs CPU) - check next model load

**Baseline Started:** 2025-11-25 14:59  
**Initial Memory:** 3745.8 MB  
**Chunks at start:** ~2172

**Check after 1 hour (15:59):**
- Memory usage (should be stable or growing slowly)
- Processing speed (should be 20-100 chars/sec)
- Device logs when TTS model reloads

### Phase 2: Trend Analysis (3 hours)

**Track:**
- Memory growth rate (MB per chunk)
- Performance degradation (chars/sec over time)
- Chapter-by-chapter comparison

**Checkpoints:**
- **Hour 1:** Memory + speed
- **Hour 2:** Memory + speed  
- **Hour 3:** Memory + speed

**Expected:**
- **No leak:** Memory stable around 3.5-4 GB
- **Leak present:** Memory growing 10-50 MB per hour

### Phase 3: Pattern Identification

**Look for correlations:**
- Does memory grow with each chunk?
- Does speed decrease as memory grows?
- Does speed reset after model reload?
- Do certain chapters cause more memory growth?

---

## Monitoring Commands

### Real-Time Performance Monitor
```bash
cd /Users/hjewkes/Documents/projects/audiobook
python scripts/monitor_performance.py
```

**Shows:**
- Recent chunk completion times
- Rolling average chars/sec
- ETA to completion
- Performance status (SLOW/OK/GOOD)

### Memory Log Viewer
```bash
# Watch memory logs in real-time
tail -f logs/queue_processor.log | grep "📊 Memory"

# Get all memory logs
grep "📊 Memory" logs/queue_processor.log
```

### Performance Log Viewer
```bash
# Recent completions
tail -20 logs/queue_processor.log | grep "✅ Processed"

# Count completions per chapter
grep "✅ Processed job: book_58187/chapter" logs/queue_processor.log | \
  cut -d'/' -f2 | cut -d'_' -f1 | sort | uniq -c
```

### System Resource Monitor
```bash
# Watch Python process
watch -n 5 'ps aux | grep "python.*uvicorn" | grep -v grep'

# Memory only
watch -n 5 'ps aux | grep "python.*uvicorn" | grep -v grep | awk "{print \$4\"% \", \$6/1024\"MB\"}"'
```

---

## Expected Behaviors

### Normal (No Leak)

| Time | Memory | Chunks | Speed |
|------|--------|--------|-------|
| Start | ~3.7 GB | 2172 | 20-50 chars/sec |
| +1hr | ~3.8 GB | +50-200 | 20-50 chars/sec |
| +2hr | ~3.9 GB | +100-400 | 20-50 chars/sec |
| +3hr | ~4.0 GB | +150-600 | 20-50 chars/sec |

**Pattern:** Memory growth < 100 MB/hour, speed constant

### Memory Leak Present

| Time | Memory | Chunks | Speed |
|------|--------|--------|-------|
| Start | ~3.7 GB | 2172 | 20-50 chars/sec |
| +1hr | ~4.5 GB | +50-200 | 15-40 chars/sec |
| +2hr | ~5.5 GB | +100-400 | 10-30 chars/sec |
| +3hr | ~6.5+ GB | +150-600 | 5-20 chars/sec |

**Pattern:** Memory growth > 300 MB/hour, speed decreasing

### TTS Model Cache Issue

| Time | Memory | Chunks | Speed |
|------|--------|--------|-------|
| Start | ~3.7 GB | 2172 | 20-50 chars/sec |
| +20min | ~8.0 GB | +20-50 | 5-10 chars/sec |
| +40min | ~8.0 GB | +40-100 | 5-10 chars/sec |
| +60min | ~8.0 GB | +60-150 | 5-10 chars/sec |

**Pattern:** Memory jumps then plateaus, speed consistently slow

---

## Potential Leak Sources

### 1. PyTorch/XTTS Model Cache
**Symptoms:**
- Memory grows with each synthesis
- Not released after chunk completes
- MPS/CUDA tensors not freed

**Detection:**
- Memory grows proportionally to chunks processed
- Larger jumps on longer chunks

**Fix:**
- Explicit cache clearing after synthesis
- Reduce batch size
- Force garbage collection

### 2. Audio File Buffers
**Symptoms:**
- Memory grows with audio file size
- WAV buffers not released

**Detection:**
- Memory correlates with audio duration
- Grows more on longer chunks

**Fix:**
- Ensure file handles closed
- Clear audio buffers explicitly

### 3. Speaker WAV Loading
**Symptoms:**
- Speaker reference loaded multiple times
- Not cached properly

**Detection:**
- Memory jumps at synthesis start
- Multiple "Loading" messages in logs

**Fix:**
- Cache speaker WAV in memory once
- Reuse cached version

### 4. Logging/Queue State
**Symptoms:**
- Log buffers growing
- Job history not pruned

**Detection:**
- Memory grows steadily regardless of chunk size
- Correlates with log file size

**Fix:**
- Rotate logs more frequently
- Prune completed job history

---

## Diagnostic Queries

### Memory per Chapter
```sql
SELECT 
    chapter_number,
    COUNT(*) as chunks,
    AVG(generation_time_seconds) as avg_time,
    AVG(text_end - text_start) as avg_chars
FROM chunks 
WHERE status='completed' 
GROUP BY chapter_number 
ORDER BY chapter_number;
```

### Slowest Chunks
```sql
SELECT 
    chapter_number,
    'index',
    generation_time_seconds,
    (text_end - text_start) as chars,
    generation_time_seconds / (text_end - text_start) as sec_per_char
FROM chunks 
WHERE status='completed' 
    AND generation_time_seconds > 100
ORDER BY generation_time_seconds DESC 
LIMIT 20;
```

### Memory Growth Correlation
```bash
# Extract memory logs with timestamps
grep "📊 Memory" logs/queue_processor.log | \
  awk '{print $1, $2, $5, $8}' | \
  sed 's/|//g' > /tmp/memory_log.txt

# Plot or analyze memory_log.txt
```

---

## Next Steps Based on Findings

### If Speed Improved (TTS_NUM_THREADS helped)
✅ **Continue monitoring for 3 hours**
- If no leak → Document success
- If leak present → Investigate sources

### If Speed Still Slow (< 20 chars/sec)
🔍 **Check device:**
1. Look for TTS device logs on next model reload
2. Run `python scripts/check_tts_device.py` (needs model loaded)
3. If on CPU fallback → Investigate why MPS failed

### If Memory Growing Rapidly (> 300 MB/hour)
🔴 **Leak present:**
1. Identify which chunks cause largest growth
2. Check PyTorch tensor caching
3. Add explicit garbage collection after synthesis
4. Consider restarting processor periodically

### If Memory Stable BUT Speed Degrading
🔍 **Thermal/CPU throttling:**
1. Check system temperature
2. Monitor CPU frequency
3. May need cooldown periods

---

## Auto-Restart Strategy (If Leak Confirmed)

If memory leak is confirmed and not easily fixable:

**Option 1: Periodic Restart**
```python
# In job_queue.py, after N chunks:
if self._chunks_processed_since_start > 100:
    logger.info("Restarting processor to clear memory...")
    return  # Exit processor, will restart
```

**Option 2: Memory Threshold**
```python
# Check memory usage
if PSUTIL_AVAILABLE:
    mem_mb = psutil.Process().memory_info().rss / 1024 / 1024
    if mem_mb > 6000:  # > 6GB
        logger.warning(f"Memory high ({mem_mb:.1f} MB), restarting...")
        return
```

---

## Current Status

**Monitoring Started:** 2025-11-25 14:59  
**Initial Conditions:**
- Memory: 3745.8 MB
- Chunks completed: ~2172
- TTS_NUM_THREADS: 14
- TTS_GPU: true

**Next Checkpoint:** 2025-11-25 15:59 (1 hour)

**Run this to monitor:**
```bash
python scripts/monitor_performance.py
```

---

## Conclusion

Memory leak detection and device logging are now in place. Monitor for 1-3 hours to identify:
1. Whether TTS_NUM_THREADS improved speed
2. Whether memory is leaking (growth rate)
3. Which device is actually being used (MPS vs CPU)
4. Correlation between memory and performance

The monitoring script will provide real-time feedback on performance trends.




