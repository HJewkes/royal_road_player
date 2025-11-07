#!/usr/bin/env python3
"""Regenerate chunk metadata with text positions for existing chunks."""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker
from src.tts.chunker import chunk_text_by_paragraphs

def regenerate_chunk_metadata(book_id: str = None):
    """Regenerate chunk metadata for all books or a specific book."""
    settings = get_settings()
    books_dir = settings.books_dir
    
    books_to_process = []
    
    if book_id:
        # Find specific book
        for book_dir in books_dir.iterdir():
            if not book_dir.is_dir():
                continue
            metadata_path = book_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        books_to_process.append(book_dir)
                        break
                except Exception:
                    continue
    else:
        # Process all books
        for book_dir in books_dir.iterdir():
            if not book_dir.is_dir():
                continue
            metadata_path = book_dir / "metadata.json"
            if metadata_path.exists():
                books_to_process.append(book_dir)
    
    for book_dir in books_to_process:
        print(f"\nProcessing: {book_dir.name}")
        tracker = MetadataTracker(book_dir)
        metadata = tracker.load()
        
        chapters_dir = book_dir / "chapters"
        if not chapters_dir.exists():
            continue
        
        # Process each chapter
        for chapter_meta in metadata.get('chapters', []):
            chapter_title = chapter_meta.get('title')
            if not chapter_title:
                continue
            
            # Check if chapter has chunks
            chunk_count = chapter_meta.get('chunk_count', 0)
            if chunk_count == 0:
                continue
            
            # Find text file
            text_file = chapters_dir / f"{chapter_title}.txt"
            if not text_file.exists():
                print(f"  ⚠️  Skipping {chapter_title}: text file not found")
                continue
            
            # Find chunk files
            chunk_files = sorted(chapters_dir.glob(f"{chapter_title}_chunk_*.wav"))
            if not chunk_files:
                print(f"  ⚠️  Skipping {chapter_title}: no chunk files found")
                continue
            
            print(f"  📄 Processing {chapter_title}: {len(chunk_files)} chunks")
            
            # Extract chunk indices from filenames
            existing_chunk_indices = set()
            for chunk_file in chunk_files:
                try:
                    chunk_num_str = chunk_file.stem.rsplit('_chunk_', 1)[-1]
                    chunk_index = int(chunk_num_str)
                    existing_chunk_indices.add(chunk_index)
                except ValueError:
                    continue
            
            # Read text
            text_content = text_file.read_text(encoding='utf-8')
            
            # Re-chunk text to get positions
            # Use same parameters as generator (target ~1 minute chunks)
            # Generator uses: target_chars = int(chunk_duration_minutes * 800) = 800 for 1.0 min
            # and max_chars = 250 (XTTS v2 limit)
            target_chars = 800  # Match generator's target_chars
            max_chars = 250  # XTTS v2 character limit
            
            chunk_data = chunk_text_by_paragraphs(
                text_content,
                target_chars_per_minute=target_chars,
                min_chars=int(target_chars * 0.3),
                max_chars=max_chars,
                return_positions=True,
            )
            
            # Build chunk metadata for ALL chunks (both existing and pending)
            # This allows the UI to show gaps and pending chunks properly
            chunk_metadata = []
            for i, chunk_info in enumerate(chunk_data, 1):
                if isinstance(chunk_info, tuple):
                    chunk_text, start_pos, end_pos = chunk_info
                else:
                    chunk_text = chunk_info
                    # Try to find position in text
                    start_pos = text_content.find(chunk_text)
                    end_pos = start_pos + len(chunk_text) if start_pos >= 0 else len(chunk_text)
                
                # Check if chunk file exists
                chunk_file = chapters_dir / f"{chapter_title}_chunk_{i:03d}.wav"
                chunk_exists = chunk_file.exists()
                
                # Load existing metadata if available (to preserve generation times, etc.)
                existing_meta = next(
                    (m for m in chapter_meta.get('chunk_metadata', []) if m.get('index') == i),
                    {}
                )
                
                chunk_metadata.append({
                    'index': i,
                    'text_start': start_pos,
                    'text_end': end_pos,
                    'text_length': len(chunk_text),
                    'status': 'completed' if chunk_exists else 'pending',
                    'generation_time_seconds': existing_meta.get('generation_time_seconds') if chunk_exists else None,
                    'created_at': existing_meta.get('created_at') if chunk_exists else None,
                })
            
            # Update metadata
            tracker.update_chunk_metadata(chapter_title, chunk_metadata)
            completed_count = sum(1 for cm in chunk_metadata if cm.get('status') == 'completed')
            pending_count = sum(1 for cm in chunk_metadata if cm.get('status') == 'pending')
            print(f"    ✅ Updated metadata for {len(chunk_metadata)} chunks ({completed_count} completed, {pending_count} pending)")
            
            # Also update chunk count to reflect only completed chunks
            tracker.update_chunk_count(chapter_title, completed_count)
    
    print("\n✅ Done!")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Regenerate chunk metadata with text positions')
    parser.add_argument('--book-id', help='Specific book ID to process (optional)')
    args = parser.parse_args()
    
    regenerate_chunk_metadata(book_id=args.book_id)

