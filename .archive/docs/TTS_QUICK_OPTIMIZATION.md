# TTS Quick Optimization Guide

## Quick Start - Enable GPU/MPS Acceleration

Since you have Apple Silicon (MPS available), you can get **2-3x speedup** immediately:

### Step 1: Enable MPS Acceleration

Add to your `.env` file:

```bash
TTS_GPU=true
```

### Step 2: Optimize CPU Threads (if staying on CPU)

If you prefer CPU mode or want to optimize it:

```bash
# Check your CPU cores
sysctl -n hw.ncpu

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

## Expected Performance Improvements

### With MPS Enabled (Apple Silicon)
- **Before:** ~50-100 chars/sec (CPU)
- **After:** ~150-300 chars/sec (MPS)
- **Speedup:** 2-3x faster
- **Example:** 8s/chunk → 3-4s/chunk

### With Optimized CPU Threads
- **Before:** Default thread count
- **After:** Optimized for your CPU
- **Speedup:** 10-20% improvement
- **Example:** 8s/chunk → 7s/chunk

## Current Settings Check

Check what's currently configured:

```bash
# Check .env file
grep TTS .env

# Check if MPS is available
python3 -c "import torch; print('MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available())"
```

## Monitoring Performance

After enabling optimizations, monitor:

1. **Generation time per chunk** (should decrease)
2. **Characters per second** (should increase)
3. **System resources** (CPU/GPU usage)

The queue status will show updated `avg_time_per_chunk` as it processes more chunks.

## Troubleshooting

### MPS Not Working
- Check PyTorch version: `python3 -c "import torch; print(torch.__version__)"`
- Should be >= 1.12 for MPS support
- Restart server after changing `.env`

### No Performance Improvement
- Verify MPS is actually being used (check logs for "MPS detected")
- Check system load (other processes using GPU?)
- Monitor with Activity Monitor (macOS) or `htop`

### Out of Memory
- MPS uses unified memory (system RAM)
- Close other applications
- Reduce `TTS_NUM_THREADS` if set too high

## Advanced Settings

See `docs/TTS_OPTIMIZATION_GUIDE.md` for:
- Process priority tuning
- CPU affinity
- Memory management
- Model warmup
- Batch processing strategies



