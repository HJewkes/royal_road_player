#!/usr/bin/env python3
"""Script to chunk chapter 1 and update metadata."""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from src.services.chunking_service import ChunkingService
from src.utils.config import get_settings

def main():
    """Chunk chapter 1 for the test book."""
    settings = get_settings()
    book_id = "book_58187"
    chapter_number = 1
    
    print(f"Chunking chapter {chapter_number} for book {book_id}...")
    
    service = ChunkingService()
    
    try:
        result = service.chunk_chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_duration_minutes=1.0,
            max_chars=250,  # XTTS v2 limit
        )
        
        print(f"✅ Successfully chunked chapter {chapter_number}")
        print(f"   Created {result.chunk_count} chunks")
        print(f"   Total text length: {result.total_text_length} characters")
        
        # Show first few chunks
        if result.chunks:
            print("\nFirst 5 chunks:")
            for chunk in result.chunks[:5]:
                print(f"   Chunk {chunk.index}: {chunk.text_length} chars, status={chunk.status.value}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())



