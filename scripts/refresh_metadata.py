"""Refresh metadata for existing books by scanning filesystem."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker


def refresh_all_books():
    """Refresh metadata for all books."""
    settings = get_settings()
    books_dir = settings.books_dir
    
    if not books_dir.exists():
        print(f"Books directory not found: {books_dir}")
        return
    
    print(f"📚 Refreshing metadata for all books in: {books_dir}\n")
    
    book_dirs = [d for d in books_dir.iterdir() if d.is_dir()]
    
    if not book_dirs:
        print("No books found.")
        return
    
    for book_dir in sorted(book_dirs):
        print(f"📖 Processing: {book_dir.name}")
        
        try:
            tracker = MetadataTracker(book_dir)
            tracker.refresh_from_filesystem()
            stats = tracker.get_stats()
            
            scraping = stats.get('scraping', {})
            tts = stats.get('tts', {})
            chunks = stats.get('chunks', {})
            
            print(f"   ✅ Scraped: {scraping.get('scraped_chapters', 0)}/{scraping.get('total_chapters', 0)}")
            print(f"   🎵 Audio: {tts.get('generated_chapters', 0)}/{scraping.get('total_chapters', 0)}")
            print(f"   🔊 Chunks: {chunks.get('total_chunks', 0)} total")
            print()
            
        except Exception as e:
            print(f"   ❌ Error: {e}\n")


def refresh_book(book_id: str):
    """Refresh metadata for a specific book."""
    settings = get_settings()
    books_dir = settings.books_dir
    
    if not books_dir.exists():
        print(f"Books directory not found: {books_dir}")
        return
    
    # Find book directory
    book_dir = None
    for dir_path in books_dir.iterdir():
        if dir_path.is_dir() and book_id in dir_path.name:
            metadata_path = dir_path / "metadata.json"
            if metadata_path.exists():
                import json
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        book_dir = dir_path
                        break
                except (json.JSONDecodeError, KeyError):
                    continue
    
    if not book_dir:
        print(f"Book not found: {book_id}")
        return
    
    print(f"📖 Refreshing metadata for: {book_dir.name}\n")
    
    try:
        tracker = MetadataTracker(book_dir)
        tracker.refresh_from_filesystem()
        stats = tracker.get_stats()
        
        scraping = stats.get('scraping', {})
        tts = stats.get('tts', {})
        chunks = stats.get('chunks', {})
        
        print(f"✅ Scraped: {scraping.get('scraped_chapters', 0)}/{scraping.get('total_chapters', 0)}")
        print(f"🎵 Audio: {tts.get('generated_chapters', 0)}/{scraping.get('total_chapters', 0)}")
        print(f"🔊 Chunks: {chunks.get('total_chunks', 0)} total")
        
        # Show chunk breakdown by chapter
        chunks_by_chapter = chunks.get('chunks_by_chapter', {})
        if chunks_by_chapter:
            print(f"\nChunk breakdown:")
            for chapter_title, chunk_count in sorted(chunks_by_chapter.items()):
                print(f"   {chapter_title}: {chunk_count} chunks")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        book_id = sys.argv[1]
        refresh_book(book_id)
    else:
        refresh_all_books()

