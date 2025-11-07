"""Monitor TTS audio generation progress."""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def find_chunk_files(chapter_path: Path) -> list[Path]:
    """Find all chunk files for a chapter."""
    chapter_dir = chapter_path.parent
    base_name = chapter_path.stem
    
    chunk_files = sorted(
        chapter_dir.glob(f"{base_name}_chunk_*.wav"),
        key=lambda p: int(p.stem.split("_chunk_")[-1])
    )
    return chunk_files


def get_chunk_number(filename: str) -> int:
    """Extract chunk number from filename."""
    try:
        return int(filename.split("_chunk_")[-1].split(".")[0])
    except (ValueError, IndexError):
        return 0


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def monitor_generation(chapter_path: str, refresh_interval: int = 5):
    """Monitor audio generation progress."""
    chapter_path = Path(chapter_path)
    
    if not chapter_path.exists():
        print(f"❌ Chapter file not found: {chapter_path}")
        return 1
    
    print(f"📊 Monitoring audio generation for: {chapter_path.name}")
    print(f"   Refresh interval: {refresh_interval} seconds")
    print(f"{'='*70}\n")
    
    # Find expected total chunks (from log or estimate)
    # We'll detect it from the highest chunk number we see
    max_chunk_seen = 0
    last_file_count = 0
    start_time = time.time()
    
    try:
        while True:
            chunk_files = find_chunk_files(chapter_path)
            current_count = len(chunk_files)
            
            if chunk_files:
                max_chunk_seen = max(max_chunk_seen, get_chunk_number(chunk_files[-1].name))
            
            # Estimate total chunks (if we haven't seen the pattern yet, use max_seen + 5)
            estimated_total = max(max_chunk_seen + 5, current_count + 1)
            
            # Calculate progress
            progress_pct = (current_count / estimated_total * 100) if estimated_total > 0 else 0
            
            # Get latest file info
            latest_file = chunk_files[-1] if chunk_files else None
            latest_size_mb = latest_file.stat().st_size / (1024 * 1024) if latest_file else 0
            
            # Calculate timing
            elapsed = time.time() - start_time
            if current_count > 0:
                avg_time_per_chunk = elapsed / current_count
                remaining_chunks = estimated_total - current_count
                estimated_remaining = avg_time_per_chunk * remaining_chunks
            else:
                avg_time_per_chunk = 0
                estimated_remaining = 0
            
            # Check if process is still running
            import subprocess
            process_running = False
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "generate_audio.py"],
                    capture_output=True,
                    text=True
                )
                process_running = result.returncode == 0
            except Exception:
                pass
            
            # Display status
            timestamp = datetime.now().strftime("%H:%M:%S")
            status_icon = "🔄" if process_running else "⏸️"
            
            print(f"\r[{timestamp}] {status_icon} Chunks: {current_count}/{estimated_total} "
                  f"({progress_pct:.1f}%) | "
                  f"Latest: {latest_file.name if latest_file else 'None'} ({latest_size_mb:.1f}MB) | "
                  f"Elapsed: {format_duration(elapsed)} | "
                  f"ETA: {format_duration(estimated_remaining)}", end="", flush=True)
            
            # Show new files
            if current_count > last_file_count:
                new_files = chunk_files[last_file_count:]
                print(f"\n   ✅ New: {', '.join(f.name for f in new_files)}")
                last_file_count = current_count
            
            # Check if we're done (no process running and we have files)
            if not process_running and current_count > 0:
                # Wait a bit to see if more files appear
                time.sleep(refresh_interval)
                final_files = find_chunk_files(chapter_path)
                if len(final_files) == current_count:
                    print(f"\n\n✅ Generation complete! {len(final_files)} chunks generated.")
                    break
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Monitoring stopped.")
        print(f"   Generated {len(find_chunk_files(chapter_path))} chunks so far.")
        return 0
    
    return 0


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor TTS audio generation progress")
    parser.add_argument(
        "chapter_path",
        type=str,
        help="Path to chapter text file",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Refresh interval in seconds (default: 5)",
    )
    
    args = parser.parse_args()
    
    return monitor_generation(args.chapter_path, args.interval)


if __name__ == "__main__":
    sys.exit(main())

