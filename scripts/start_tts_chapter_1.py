#!/usr/bin/env python3
"""Queue and start TTS processing for chapter 1."""

import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from src.services.job_queue import ChunkJobQueue

async def main():
    """Queue chunks and start processing."""
    book_id = "book_58187"
    chapter_number = 1
    
    print("=" * 70)
    print("Starting TTS Processing for Chapter 1")
    print("=" * 70)
    
    queue = ChunkJobQueue()
    
    # Clear any existing queue
    print("\n1. Clearing any existing queue...")
    queue.clear_queue()
    
    # Queue chunks
    print(f"\n2. Queueing chunks from chapter {chapter_number}...")
    added = queue.enqueue_chapter_chunks(
        book_id=book_id,
        chapter_number=chapter_number,
    )
    print(f"   ✅ Queued {added} chunks")
    
    # Show initial status
    status = queue.get_queue_status()
    print(f"\n3. Queue Status:")
    print(f"   Total: {status['total']}")
    print(f"   Pending: {status['pending']}")
    
    # Ask if user wants to start processing
    print("\n4. Queue is ready!")
    print("   Options:")
    print("   a) Process all jobs now (this will take a while)")
    print("   b) Process one job as a test")
    print("   c) Just queue (you can process later via API)")
    
    choice = input("\n   Your choice (a/b/c): ").strip().lower()
    
    if choice == 'a':
        print("\n5. Processing all jobs...")
        print("   (This will take a while - you can monitor with: python scripts/monitor_queue.py)")
        stats = await queue.process_all()
        print(f"\n✅ Processing complete!")
        print(f"   Processed: {stats['processed']}")
        print(f"   Completed: {stats['completed']}")
        print(f"   Failed: {stats['failed']}")
    
    elif choice == 'b':
        print("\n5. Processing one job as test...")
        job = await queue.process_next()
        if job:
            print(f"   ✅ Processed: chunk_{job.chunk_index}")
            print(f"   Status: {job.status.value}")
            if job.error:
                print(f"   Error: {job.error}")
        else:
            print("   No jobs to process")
        
        # Show updated status
        status = queue.get_queue_status()
        print(f"\n   Updated Status:")
        print(f"   Pending: {status['pending']}")
        print(f"   Completed: {status['completed']}")
    
    else:
        print("\n5. Jobs queued. You can process them via:")
        print("   - API: POST /api/queue/process")
        print("   - Script: python scripts/monitor_queue.py (then process via API)")
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())



