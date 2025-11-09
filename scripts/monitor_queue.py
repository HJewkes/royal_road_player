#!/usr/bin/env python3
"""Monitor job queue progress in real-time."""

import sys
import time
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from src.services.job_queue import ChunkJobQueue

def format_time(seconds: int) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def print_status(queue: ChunkJobQueue):
    """Print formatted queue status."""
    status = queue.get_queue_status()
    
    print("\n" + "=" * 70)
    print("QUEUE STATUS")
    print("=" * 70)
    
    # Progress bar
    progress = status['progress_percent']
    bar_width = 50
    filled = int(bar_width * progress / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"\nProgress: [{bar}] {progress:.1f}%")
    
    # Statistics
    print(f"\nTotal Jobs:    {status['total']}")
    print(f"  ✅ Completed: {status['completed']}")
    print(f"  ⏳ Pending:   {status['pending']}")
    print(f"  🔄 Running:    {status['running']}")
    print(f"  ❌ Failed:     {status['failed']}")
    
    # Current job
    if status['current_job']:
        job = status['current_job']
        print(f"\n🔄 Current Job:")
        print(f"   {job['book_id']}/{job['chapter_number']}/chunk_{job['chunk_index']}")
    
    # Estimated time
    if status['estimated_seconds_remaining'] > 0:
        time_str = format_time(status['estimated_seconds_remaining'])
        print(f"\n⏱️  Estimated Time Remaining: {time_str}")
    
    # Processing status
    if status['is_processing']:
        print("\n⚙️  Status: PROCESSING")
    elif status['pending'] > 0:
        print("\n⏸️  Status: IDLE (jobs pending)")
    else:
        print("\n✅ Status: COMPLETE")
    
    print("=" * 70)

def print_progress_details(queue: ChunkJobQueue):
    """Print detailed progress information."""
    details = queue.get_progress_details()
    
    print("\n" + "=" * 70)
    print("DETAILED PROGRESS")
    print("=" * 70)
    
    # Recent completed
    if details['recent_completed']:
        print(f"\n✅ Recent Completed ({len(details['recent_completed'])}):")
        for job in details['recent_completed'][-5:]:  # Show last 5
            print(f"   Chunk {job['chunk_index']} - {job['created_at']}")
    
    # Recent failed
    if details['recent_failed']:
        print(f"\n❌ Recent Failed ({len(details['recent_failed'])}):")
        for job in details['recent_failed'][-5:]:  # Show last 5
            print(f"   Chunk {job['chunk_index']}: {job.get('error', 'Unknown error')}")
    
    # Next pending
    if details['next_pending']:
        print(f"\n⏳ Next Pending ({len(details['next_pending'])}):")
        for job in details['next_pending'][:5]:  # Show first 5
            print(f"   Chunk {job['chunk_index']}")
    
    print("=" * 70)

def main():
    """Monitor queue progress."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor job queue progress")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Update interval in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed progress information"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Show status once and exit"
    )
    
    args = parser.parse_args()
    
    queue = ChunkJobQueue()
    
    try:
        if args.once:
            print_status(queue)
            if args.detailed:
                print_progress_details(queue)
        else:
            print("Monitoring queue progress (Ctrl+C to stop)...")
            print(f"Update interval: {args.interval}s\n")
            
            while True:
                # Clear screen (works on most terminals)
                print("\033[2J\033[H", end="")
                
                print_status(queue)
                if args.detailed:
                    print_progress_details(queue)
                
                time.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()



