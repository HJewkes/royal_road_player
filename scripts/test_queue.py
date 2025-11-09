#!/usr/bin/env python3
"""Test script to demonstrate the job queue system."""

import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from src.services.job_queue import ChunkJobQueue

async def main():
    """Test the job queue system."""
    book_id = "book_58187"
    chapter_number = 1
    
    print("=" * 60)
    print("Job Queue System Test")
    print("=" * 60)
    
    # Create queue
    queue = ChunkJobQueue()
    
    # Clear any existing queue
    print("\n1. Clearing any existing queue...")
    queue.clear_queue()
    
    # Queue chunks from chapter 1
    print(f"\n2. Queueing chunks from chapter {chapter_number}...")
    added = queue.enqueue_chapter_chunks(
        book_id=book_id,
        chapter_number=chapter_number,
        chunk_indices=None,  # Queue all pending chunks
    )
    print(f"   ✅ Added {added} jobs to queue")
    
    # Show queue status
    print("\n3. Queue status:")
    status = queue.get_queue_status()
    print(f"   Total jobs: {status['total']}")
    print(f"   Pending: {status['pending']}")
    print(f"   Running: {status['running']}")
    print(f"   Completed: {status['completed']}")
    print(f"   Failed: {status['failed']}")
    
    # Show first few jobs
    print("\n4. First 5 jobs in queue:")
    jobs = queue.get_queue()
    for job in jobs[:5]:
        print(f"   Job: {job['book_id']}/{job['chapter_number']}/chunk_{job['chunk_index']} - {job['status']}")
    
    # Ask user if they want to process
    print("\n5. Queue is ready for processing!")
    print("   You can now:")
    print("   - Call POST /api/queue/process/next to process one job")
    print("   - Call POST /api/queue/process to process all jobs")
    print("   - Check status with GET /api/queue/status")
    
    # Optionally process one job as a test
    response = input("\n   Process one job as a test? (y/n): ").strip().lower()
    if response == 'y':
        print("\n6. Processing one job...")
        job = await queue.process_next()
        if job:
            print(f"   ✅ Processed: {job.book_id}/{job.chapter_number}/chunk_{job.chunk_index}")
            print(f"   Status: {job.status.value}")
            if job.error:
                print(f"   Error: {job.error}")
        else:
            print("   No jobs to process")
        
        # Show updated status
        print("\n7. Updated queue status:")
        status = queue.get_queue_status()
        print(f"   Total jobs: {status['total']}")
        print(f"   Pending: {status['pending']}")
        print(f"   Running: {status['running']}")
        print(f"   Completed: {status['completed']}")
        print(f"   Failed: {status['failed']}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())



