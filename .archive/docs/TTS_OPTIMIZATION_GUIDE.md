# TTS Optimization Guide

> **Date:** 2025-11-08  
> **Purpose:** Maximize TTS performance for long-term processing

## Overview

This guide covers tunable settings and optimization strategies for XTTS v2 to maximize performance, especially for long-term batch processing of audiobook chapters.

## Quick Start - Enable GPU/MPS Acceleration

If you have Apple Silicon (MPS available) or NVIDIA GPU, you can get **2-3x speedup** immediately:

### Step 1: Enable GPU/MPS Acceleration

Add to your `.env` file:

```bash
TTS_GPU=true
```

### Step 2: Optimize CPU Threads (if staying on CPU)

If you prefer CPU mode or want to optimize it:

```bash
# Check your CPU cores
sysctl -n hw.ncpu  # macOS
nproc  # Linux

# Set threads (leave 1-2 cores free for system)
TTS_NUM_THREADS=6  # For 8-core CPU
```

### Step 3: Restart Server

```bash
# Kill existing server
pkill -f uvicorn

# Restart
make dev-all
```

### Expected Performance Improvements

**With MPS Enabled (Apple Silicon):**
- **Before:** ~50-100 chars/sec (CPU)
- **After:** ~150-300 chars/sec (MPS)
- **Speedup:** 2-3x faster
- **Example:** 8s/chunk → 3-4s/chunk

**With Optimized CPU Threads:**
- **Before:** Default thread count
- **After:** Optimized for your CPU
- **Speedup:** 10-20% improvement
- **Example:** 8s/chunk → 7s/chunk

### Current Settings Check

Check what's currently configured:

```bash
# Check .env file
grep TTS .env

# Check if MPS is available (macOS)
python3 -c "import torch; print('MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available())"

# Check if CUDA is available (NVIDIA)
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Troubleshooting Quick Fixes

**MPS Not Working:**
- Check PyTorch version: `python3 -c "import torch; print(torch.__version__)"`
- Should be >= 1.12 for MPS support
- Restart server after changing `.env`

**No Performance Improvement:**
- Verify GPU is actually being used (check logs for "MPS detected" or "CUDA detected")
- Check system load (other processes using GPU?)
- Monitor with Activity Monitor (macOS) or `htop`

**Out of Memory:**
- MPS uses unified memory (system RAM) - close other applications
- CUDA uses VRAM - reduce batch size or close GPU-intensive apps
- Reduce `TTS_NUM_THREADS` if set too high

---

## Hardware Acceleration

### GPU Support (NVIDIA CUDA)

If you have an NVIDIA GPU with CUDA support:

```bash
# In .env file
TTS_GPU=true
```

**Expected Performance:**
- CPU: ~50-100 chars/sec
- GPU: ~200-500 chars/sec (4-5x faster)
- Memory: ~2-4 GB VRAM

### Apple Silicon (MPS)

If you have an Apple Silicon Mac (M1/M2/M3), MPS acceleration is available:

```bash
# In .env file
TTS_GPU=true  # Will use MPS on Apple Silicon
```

**Expected Performance:**
- CPU: ~50-100 chars/sec
- MPS: ~150-300 chars/sec (2-3x faster)
- Memory: Unified memory (uses system RAM)

### CPU Optimization

For CPU-only systems, optimize thread usage:

```bash
# In .env file
TTS_NUM_THREADS=4  # Match your CPU cores
OMP_NUM_THREADS=4  # OpenMP threads
```

**Recommendations:**
- Set to number of physical cores (not hyperthreads)
- Leave 1-2 cores free for system
- Example: 8-core CPU → use 6-7 threads

## Model Configuration Options

### Available TTS Parameters

The TTS engine accepts these optimization parameters:

```python
TTS(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2",
    gpu=True,  # Use GPU/MPS if available
    progress_bar=True  # Show progress
)
```

### Synthesis Parameters

```python
tts.tts_to_file(
    text=text,
    speaker_wav=speaker_path,
    language="en",
    speed=1.0,  # 0.5-2.0 range
    split_sentences=True,  # Process sentences separately (faster)
    # Additional kwargs available
)
```

## Tunable Settings

### 1. Device Selection

**Current:** Auto-detects (CPU by default)  
**Optimization:** Explicitly set GPU/MPS

```python
# In engine.py
self._tts = TTS(
    model_name=self.settings.tts_model,
    gpu=self.settings.tts_gpu,  # Add this
    progress_bar=True
)
```

### 2. Threading (CPU Mode)

**Current:** Uses PyTorch defaults  
**Optimization:** Set optimal thread count

```python
import torch
torch.set_num_threads(settings.tts_num_threads)
```

### 3. Model Precision

**Current:** Full precision (float32)  
**Optimization:** Use half precision (float16) on GPU

```python
# In synthesis
kwargs = {
    "text": text,
    "file_path": str(output_path),
    "language": language,
    "speaker_wav": speaker,
    "speed": speed,
}
# Add precision control if available
if self.settings.tts_gpu:
    kwargs["use_cuda"] = True
```

### 4. Batch Processing

**Current:** One chunk at a time  
**Optimization:** Process multiple chunks if memory allows

**Note:** XTTS v2 doesn't support batch synthesis natively, but you could:
- Process chunks in parallel (separate processes)
- Use async processing with multiple workers

### 5. Memory Management

**Current:** Model stays loaded in memory  
**Optimization:** 
- Keep model loaded (already optimal)
- Clear GPU cache between chunks if needed
- Use gradient checkpointing (if available)

## Configuration File Updates

Add these to `.env`:

```bash
# GPU/Device Settings
TTS_GPU=false  # Set to true if you have GPU/MPS
TTS_NUM_THREADS=4  # CPU threads (match your cores)

# Model Settings
TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
TTS_SPEED=1.0

# Performance Settings
TTS_SPLIT_SENTENCES=true  # Process sentences separately (faster)
TTS_USE_HALF_PRECISION=false  # Use float16 on GPU (faster, slightly lower quality)
```

## Long-Term Processing Optimizations

### 1. Process Priority

Set higher priority for TTS process:

```bash
# Linux/Mac
nice -n -10 python -m uvicorn src.web.app:app

# Or in Python
import os
os.nice(-10)  # Higher priority (requires root on some systems)
```

### 2. CPU Affinity

Pin process to specific cores:

```bash
# Linux
taskset -c 0-3 python -m uvicorn src.web.app:app

# Or in Python
import os
os.sched_setaffinity(0, {0, 1, 2, 3})  # Use cores 0-3
```

### 3. Memory Pre-allocation

Pre-allocate memory to avoid fragmentation:

```python
# In engine initialization
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    # Pre-allocate
    dummy = torch.zeros(1).cuda()
    del dummy
```

### 4. Model Warmup

Warm up the model before processing:

```python
# After loading model
self._tts.tts_to_file(
    text="This is a warmup sentence.",
    file_path="/tmp/warmup.wav",
    speaker_wav=speaker,
    language="en"
)
```

## Monitoring Performance

### Track Metrics

Monitor these metrics during processing:

1. **Generation Time per Chunk**
   - Current: ~8-17 seconds per chunk
   - Target: <10 seconds (with optimizations)

2. **Characters per Second**
   - Current: ~45-92ms per character
   - Target: <50ms per character (with GPU)

3. **Memory Usage**
   - Model: ~2-4 GB
   - Per chunk: ~100-500 MB
   - Monitor for leaks

4. **CPU/GPU Utilization**
   - CPU: Should be high during synthesis
   - GPU: Should be high if using GPU

### Profiling Tools

```python
# Add timing to synthesis
import time
import cProfile

profiler = cProfile.Profile()
profiler.enable()
# ... synthesis code ...
profiler.disable()
profiler.dump_stats('tts_profile.prof')
```

## Recommended Settings by Hardware

### High-End GPU (NVIDIA RTX 3080+)
```bash
TTS_GPU=true
TTS_USE_HALF_PRECISION=true
TTS_NUM_THREADS=8
```

### Apple Silicon (M1/M2/M3)
```bash
TTS_GPU=true  # Uses MPS
TTS_NUM_THREADS=6  # Leave cores for system
```

### CPU Only (8+ cores)
```bash
TTS_GPU=false
TTS_NUM_THREADS=6  # Leave 2 cores free
OMP_NUM_THREADS=6
```

### CPU Only (4 cores)
```bash
TTS_GPU=false
TTS_NUM_THREADS=3  # Leave 1 core free
OMP_NUM_THREADS=3
```

## Implementation Priority

### High Impact, Easy Implementation
1. ✅ **Enable GPU/MPS** - 2-5x speedup
2. ✅ **Set optimal thread count** - 10-20% improvement
3. ✅ **Split sentences** - Already enabled, verify it's working

### Medium Impact, Medium Effort
1. ⚠️ **Half precision on GPU** - 20-30% faster, slight quality loss
2. ⚠️ **Model warmup** - Reduces first-chunk overhead
3. ⚠️ **Process priority** - Small improvement

### Low Impact, High Effort
1. ⚠️ **Parallel processing** - Complex, requires careful memory management
2. ⚠️ **Model quantization** - May reduce quality
3. ⚠️ **Custom model** - Significant development effort

## Testing Optimizations

Before applying optimizations:

1. **Baseline Measurement**
   ```bash
   # Time 10 chunks
   time python scripts/test_tts_performance.py --chunks 10
   ```

2. **Apply Optimization**
   - Update `.env` with new setting
   - Restart server

3. **Measure Again**
   - Compare generation times
   - Check quality (listen to samples)

4. **Iterate**
   - Try different settings
   - Find optimal balance

## Current Status

**Your System:**
- ✅ MPS (Apple Silicon) available
- ⚠️ GPU not explicitly enabled
- ⚠️ Thread count not optimized

**Recommendations:**
1. Enable MPS acceleration (`TTS_GPU=true`)
2. Set thread count to 6-7 (leave cores for system)
3. Monitor performance improvements

## Next Steps

1. Add GPU/MPS support to engine
2. Add thread count configuration
3. Test with your hardware
4. Measure improvements
5. Document optimal settings for your system



