#!/usr/bin/env python3
"""Example: Monitor queue progress via API calls."""

import sys
import time
import requests
from pathlib import Path

# Add backend to path for imports if needed
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

API_BASE = "http://localhost:8000"

def get_status():
    """Get queue status from API."""
    try:
        response = requests.get(f"{API_BASE}/api/queue/status")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching status: {e}")
        return None

def get_progress():
    """Get detailed progress from API."""
    try:
        response = requests.get(f"{API_BASE}/api/queue/progress")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching progress: {e}")
        return None

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

def main():
    """Monitor queue progress via API."""
    print("Monitoring queue progress via API...")
    print(f"API Base URL: {API_BASE}\n")
    
    try:
        while True:
            status = get_status()
            if status:
                # Progress bar
                progress = status.get('progress_percent', 0)
                bar_width = 50
                filled = int(bar_width * progress / 100)
                bar = "█" * filled + "░" * (bar_width - filled)
                
                print("\033[2J\033[H", end="")  # Clear screen
                print("=" * 70)
                print("QUEUE STATUS (via API)")
                print("=" * 70)
                print(f"\nProgress: [{bar}] {progress:.1f}%")
                print(f"\nTotal: {status.get('total', 0)}")
                print(f"  ✅ Completed: {status.get('completed', 0)}")
                print(f"  ⏳ Pending:   {status.get('pending', 0)}")
                print(f"  🔄 Running:    {status.get('running', 0)}")
                print(f"  ❌ Failed:     {status.get('failed', 0)}")
                
                if status.get('current_job'):
                    job = status['current_job']
                    print(f"\n🔄 Current: chunk_{job['chunk_index']}")
                
                if status.get('estimated_seconds_remaining', 0) > 0:
                    time_str = format_time(status['estimated_seconds_remaining'])
                    print(f"\n⏱️  ETA: {time_str}")
                
                if status.get('is_processing'):
                    print("\n⚙️  Status: PROCESSING")
                elif status.get('pending', 0) > 0:
                    print("\n⏸️  Status: IDLE")
                else:
                    print("\n✅ Status: COMPLETE")
                
                print("=" * 70)
            
            time.sleep(2)
    
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



