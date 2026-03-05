# Background Processor Review & Fix

**Date:** 2025-11-25  
**Issue:** Background processor appears to not be running, logs don't appear  
**Status:** ✅ **RESOLVED** - Processor was working, but failures were silent

---

## Summary

The background processor **was already working correctly**. The issue was that:

1. **Silent startup failures** - If the async task crashed immediately, the exception would be stored in the task but never raised or logged
2. **Invisible operation** - All logging went only to `logs/queue_processor.log`, nothing to console
3. **No health monitoring** - No way to tell if the task had crashed without manually checking the task status

---

## Root Cause Analysis

### The Problem with Async Tasks

When you create an async task with `asyncio.create_task()`, if the coroutine raises an exception:

```python
task = loop.create_task(_processor())  # Task created
# If _processor() crashes immediately...
# Exception is stored in task._exception
# But nothing is raised or logged unless you:
# 1. await task
# 2. Call task.result()
# 3. Check task.exception()
```

The previous code just created the task and assumed it was running. If it crashed in the first few seconds, you'd never know.

### The Logging Problem

All processor logs used a file handler with `propagate = False`:

```python
processor_logger.propagate = False  # Don't send to console
```

This meant:
- ✅ Detailed logs in `logs/queue_processor.log`
- ❌ No console output for startup/errors
- ❌ No way to quickly see if processor was working

---

## What Was Fixed

### 1. Startup Health Check (`app.py`)

Added a check immediately after task creation:

```python
task = queue.start_background_processor(interval_seconds=1.0)
print(f"✅ Background job processor started")

# Check if task failed immediately (within first 100ms)
await asyncio.sleep(0.1)
if task.done():
    print(f"❌ WARNING: Processor task finished immediately")
    try:
        task.result()  # This will raise the exception
    except Exception as task_exc:
        print(f"❌ Processor task failed: {task_exc}")
        traceback.print_exc()
        raise RuntimeError("Background processor failed to start") from task_exc
```

**Result:** Any immediate startup failure is now visible and crashes the app startup (fail fast).

### 2. Dual Logging for Critical Events

Added console output for:
- ✅ Processor startup
- ❌ Fatal errors
- 🔥 Unhandled exceptions

```python
async def _processor():
    print("✅ Background processor task starting...")  # Console
    processor_logger.info("Background processor started")  # File
    
    try:
        # ... main loop ...
    except Exception as e:
        print(f"❌ FATAL: Background processor crashed: {e}")  # Console
        processor_logger.critical(f"FATAL: {e}", exc_info=True)  # File
        traceback.print_exc()  # Console traceback
        raise
```

**Result:** Critical errors are now visible in both console and log file.

### 3. Cleaned Up Excessive Debug Logging

The previous agent had added 40+ DEBUG log statements like:
```python
processor_logger.info("DEBUG: About to enter main while loop...")
processor_logger.info("DEBUG: Loop iteration X, checking for jobs...")
processor_logger.info("DEBUG: Calling process_next()...")
```

This was helpful for diagnosis but too noisy for production. Cleaned up to:
- Essential startup messages (INFO level)
- Job processing results (INFO level)
- Detailed diagnostics (DEBUG level - only when LOG_LEVEL=DEBUG)

**Result:** Logs are now readable and actionable.

---

## Verification

The processor is confirmed working:

```
2025-11-25 10:00:54 [INFO] Background processor started
2025-11-25 10:00:54 [INFO] Polling interval: 1.0 seconds
2025-11-25 10:01:16 [INFO] ✅ Processed job: book_58187/chapter_3/chunk_323 (status: failed)
2025-11-25 10:01:17 [DEBUG] Loop iteration 2, checking for jobs...
```

The processor:
- ✅ Starts successfully
- ✅ Continuously polls for jobs
- ✅ Processes chunks
- ✅ Handles failures gracefully (continues processing)
- ✅ Logs all activity to `logs/queue_processor.log`

---

## How to Monitor the Processor

### Check if Running

```bash
# Check process
ps aux | grep uvicorn

# Check recent activity
tail -20 logs/queue_processor.log

# Check for errors
grep -i error logs/queue_processor.log | tail -20
```

### Startup Messages

When the server starts, you should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
✅ Database initialized
✅ Background job processor started (logs: logs/queue_processor.log)
   Processor task: <Task pending>, done: False
✅ Processor task is running
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

If you see any `❌` messages or the task shows `done: True`, there's a problem.

### Health Check Endpoint

The processor status is exposed via API:

```bash
curl http://localhost:8000/api/queue/status
```

Returns:
```json
{
  "total": 1234,
  "pending": 567,
  "running": 1,
  "completed": 665,
  "failed": 1,
  "is_processing": true,
  "progress_percent": 54.23
}
```

---

## Known Issues

### Division by Zero in Chunk Processing

Found one failure during testing:
```
2025-11-25 10:01:16 [ERROR] Job failed: float division by zero
```

This is a **separate bug** in the TTS or metadata calculation code, not the processor itself. The processor correctly:
1. Caught the error
2. Marked the chunk as FAILED
3. Logged the error
4. Continued processing other chunks

**Action needed:** Investigate and fix the division by zero bug in the TTS generation pipeline.

---

## Recommendations

### 1. Keep the Health Check

The startup health check (`await asyncio.sleep(0.1)` + `task.done()` check) should stay. It catches immediate failures that would otherwise be silent.

### 2. Consider Adding a Watchdog

Add a periodic check (every 5 minutes?) to verify the processor task is still alive:

```python
# In app.py lifespan, start a watchdog
async def watchdog():
    while True:
        await asyncio.sleep(300)  # 5 minutes
        if queue._processor_task and queue._processor_task.done():
            logger.error("❌ Processor task died! Attempting restart...")
            try:
                queue._processor_task = queue.start_background_processor()
            except Exception as e:
                logger.critical(f"Failed to restart processor: {e}")
```

### 3. Monitoring Dashboard

Consider adding a `/api/health/processor` endpoint that returns:
- Task status (running/crashed)
- Last processed job timestamp
- Recent error count
- Average processing time

---

## Files Changed

- `backend/src/web/app.py` - Added health check after processor start
- `backend/src/services/job_queue.py` - Improved logging, cleaned up debug noise

All changes are backward compatible. No database or API changes.

---

## Testing

To test the processor:

```bash
# 1. Start the server
make dev

# 2. Check startup logs (should see ✅ messages)

# 3. Queue some chunks
curl -X POST http://localhost:8000/api/queue/book_58187/chapter/3/chunks

# 4. Watch logs
tail -f logs/queue_processor.log

# 5. Check status
curl http://localhost:8000/api/queue/status
```

---

## Conclusion

The background processor was working all along. The improvements made it:
- **Visible** - Console output for startup and errors
- **Robust** - Health checks catch immediate failures
- **Maintainable** - Cleaner, more focused logging

The processor is now production-ready with proper error handling and monitoring.




