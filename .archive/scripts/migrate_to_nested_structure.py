#!/usr/bin/env python3
"""Migrate audiobook data from flat structure to nested structure.

Old structure:
  data/books/{book_dir}/
    metadata.json
    chapters/
      {chapter_title}.txt
      {chapter_title}_chunk_{index}.wav

New structure:
  data/books/{book_id}/
    metadata.json
    chapters/
      {chapter_id}/
        text.txt
        metadata.json
        chunks/
          {index}/
            text.txt
            audio.wav
            metadata.json
"""

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import sys


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    # Remove special characters, replace spaces with underscores
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.lower().strip('_')


def extract_chapter_number(chapter_data: Dict[str, Any]) -> Optional[int]:
    """Extract chapter number from chapter data.
    
    Returns chapter_number if available, otherwise extracts from title pattern.
    """
    # Prefer chapter_number if available
    if chapter_data.get('chapter_number') is not None:
        return int(chapter_data['chapter_number'])
    
    # Try to extract chapter number from title pattern
    title = chapter_data.get('title', '')
    # Match patterns like "07-12 - Title" -> extract "12", "7.1 - Title" -> extract "1"
    # Prefer the second number in patterns like "07-12" (chapter number within book)
    match = re.search(r'(\d+)[\.-](\d+)', title)  # Matches "07-12" or "7.1"
    if match:
        # Return the second number (chapter number within book)
        return int(match.group(2))
    # Fallback: match single number patterns like "Chapter 12"
    match = re.search(r'(?:^|\s)(?:0*)?(\d+)(?:[\.-]|$)', title)
    if match:
        return int(match.group(1))
    
    return None


def get_chapter_id(book_id: str, chapter_data: Dict[str, Any]) -> str:
    """Generate a chapter ID from chapter data.
    
    Format: {book_id}_{chapter_number} if chapter_number available,
    otherwise falls back to Royal Road number or extracted number.
    """
    chapter_number = extract_chapter_number(chapter_data)
    
    # If we have a chapter number, use book_id + chapter_number format
    if chapter_number is not None:
        return f"{book_id}_{chapter_number:02d}"  # Zero-pad to 2 digits
    
    # Fall back to Royal Road number
    if chapter_data.get('number'):
        return str(chapter_data['number'])
    
    # Last resort: slugified title (should be rare)
    title = chapter_data.get('title', 'unknown')
    return slugify(title)


def migrate_book(book_dir: Path, output_dir: Path, dry_run: bool = False) -> None:
    """Migrate a single book to the new nested structure."""
    print(f"\n📚 Migrating book: {book_dir.name}")
    
    metadata_path = book_dir / "metadata.json"
    if not metadata_path.exists():
        print(f"  ⚠️  No metadata.json found, skipping")
        return
    
    # Load book metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        book_metadata = json.load(f)
    
    # Also try to load root metadata.json for chunk metadata (fallback)
    root_metadata_path = book_dir.parent / "metadata.json"
    root_metadata = None
    if root_metadata_path.exists():
        try:
            with open(root_metadata_path, 'r', encoding='utf-8') as f:
                root_metadata = json.load(f)
        except Exception:
            pass
    
    book_id = book_metadata.get('book_id', '')
    if not book_id:
        print(f"  ⚠️  No book_id found in metadata, skipping")
        return
    
    # Create output book directory
    output_book_dir = output_dir / book_dir.name
    if not dry_run:
        output_book_dir.mkdir(parents=True, exist_ok=True)
    
    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        print(f"  ⚠️  No chapters directory found, skipping")
        return
    
    output_chapters_dir = output_book_dir / "chapters"
    
    # Process each chapter
    chapters_processed = []
    
    # Build a map of chapters by title to merge data from multiple entries
    chapter_data_map = {}
    for chapter_data in book_metadata.get('chapters', []):
        chapter_title = chapter_data.get('title')
        if not chapter_title:
            continue
        
        # Skip test/temporary chapters (e.g., "_temp_3000" entries)
        if '_temp_' in chapter_title.lower() or chapter_title.lower().endswith('_temp'):
            print(f"  ⏭️  Skipping test/temporary chapter: {chapter_title}")
            continue
        
        # Normalize title for matching (handle variations like "7.1" vs "07-01")
        # Strategy: Extract number prefix, normalize it, then compare rest of title
        title_lower = chapter_title.lower().strip()
        # Convert dots to hyphens first
        title_lower = re.sub(r'\.', '-', title_lower)
        # Remove leading zeros from number patterns (07-02 -> 7-2)
        title_lower = re.sub(r'\b0+(\d)', r'\1', title_lower)
        # Remove special chars except hyphens and spaces
        title_cleaned = re.sub(r'[^\w\s-]', '', title_lower)
        # Normalize all hyphens and spaces to single spaces
        title_normalized = re.sub(r'[-\s]+', ' ', title_cleaned).strip()
        
        if title_normalized not in chapter_data_map:
            chapter_data_map[title_normalized] = []
        chapter_data_map[title_normalized].append(chapter_data)
    
    # Process unique chapters
    processed_titles = set()
    
    for chapter_data in book_metadata.get('chapters', []):
        chapter_title = chapter_data.get('title')
        if not chapter_title:
            continue
        
        # Skip test/temporary chapters (e.g., "_temp_3000" entries)
        if '_temp_' in chapter_title.lower() or chapter_title.lower().endswith('_temp'):
            continue
        
        # Normalize title for deduplication (same logic as above)
        title_lower = chapter_title.lower().strip()
        title_lower = re.sub(r'\.', '-', title_lower)
        title_lower = re.sub(r'\b0+(\d)', r'\1', title_lower)
        title_cleaned = re.sub(r'[^\w\s-]', '', title_lower)
        title_normalized = re.sub(r'[-\s]+', ' ', title_cleaned).strip()
        
        if title_normalized in processed_titles:
            continue
        processed_titles.add(title_normalized)
        
        # Merge data from all entries with this title
        all_chapter_data = chapter_data_map.get(title_normalized, [chapter_data])
        merged_chapter_data = {}
        for entry in all_chapter_data:
            merged_chapter_data.update({k: v for k, v in entry.items() if v is not None})
        # Prefer the entry with Royal Road number/URL if available
        preferred_entry = None
        for entry in all_chapter_data:
            if entry.get('number') or entry.get('url'):
                preferred_entry = entry
                merged_chapter_data.update(entry)
                break
        
        # Extract chapter number and generate ID
        chapter_number = extract_chapter_number(merged_chapter_data)
        chapter_id = get_chapter_id(book_id, merged_chapter_data)
        
        # Update merged_chapter_data with extracted chapter_number if not present
        if chapter_number is not None and merged_chapter_data.get('chapter_number') is None:
            merged_chapter_data['chapter_number'] = chapter_number
        
        # If we have a preferred entry with Royal Road number, use that title for consistency
        if preferred_entry:
            chapter_title = preferred_entry.get('title', chapter_title)
        
        # Use chapter number for directory name, fall back to chapter_id if no number
        if chapter_number is not None:
            chapter_dir_name = f"{chapter_number:02d}"  # Zero-pad to 2 digits
        else:
            chapter_dir_name = chapter_id  # Fallback to chapter_id
        
        print(f"  📖 Processing chapter: {chapter_title} -> {chapter_dir_name} (id: {chapter_id}, chapter_number: {chapter_number})")
        
        # Create chapter directory in output location
        chapter_dir = output_chapters_dir / chapter_dir_name
        if not dry_run:
            chapter_dir.mkdir(parents=True, exist_ok=True)
        
        # Find text file in source (try exact match first, then search for similar)
        old_text_file = chapters_dir / f"{chapter_title}.txt"
        
        if not old_text_file.exists():
            # Try to find file by matching title (case-insensitive, flexible)
            # Handle variations like "7.1" vs "07-01", "7.2" vs "07-02"
            for txt_file in chapters_dir.glob("*.txt"):
                file_base = txt_file.stem
                
                # Normalize both titles for comparison
                # Convert chapter title: "7.1 - Title" -> normalize
                chapter_title_normalized = chapter_title.lower().strip()
                chapter_title_normalized = re.sub(r'\.', '-', chapter_title_normalized)  # 7.1 -> 7-1
                chapter_title_normalized = re.sub(r'\b0+(\d)', r'\1', chapter_title_normalized)  # 07-01 -> 7-1
                chapter_title_normalized = re.sub(r'[^\w\s-]', '', chapter_title_normalized)
                chapter_title_normalized = re.sub(r'[-\s]+', ' ', chapter_title_normalized).strip()
                
                # Normalize file name: "07-01 - Title" -> normalize
                file_title_normalized = file_base.lower().strip()
                file_title_normalized = re.sub(r'\.', '-', file_title_normalized)
                file_title_normalized = re.sub(r'\b0+(\d)', r'\1', file_title_normalized)
                file_title_normalized = re.sub(r'[^\w\s-]', '', file_title_normalized)
                file_title_normalized = re.sub(r'[-\s]+', ' ', file_title_normalized).strip()
                
                # Check if normalized titles match
                if chapter_title_normalized == file_title_normalized:
                    old_text_file = txt_file
                    break
                # Also check if one contains the other (for partial matches)
                elif chapter_title_normalized in file_title_normalized or file_title_normalized in chapter_title_normalized:
                    old_text_file = txt_file
                    break
        
        new_text_file = chapter_dir / "text.txt"
        
        if old_text_file.exists():
            if not dry_run:
                shutil.copy2(str(old_text_file), str(new_text_file))
            print(f"    ✅ Copied text file: {old_text_file.name}")
        else:
            print(f"    ⚠️  Text file not found for: {chapter_title}")
            # Still create chapter directory and metadata even without text file
            if not dry_run:
                chapter_dir.mkdir(parents=True, exist_ok=True)
        
        # Read chapter text for chunk extraction and word count
        # In dry-run, use old file; after migration, use new file
        chapter_text = None
        word_count = merged_chapter_data.get('word_count')
        text_file_to_read = new_text_file if new_text_file.exists() else old_text_file
        if text_file_to_read.exists():
            chapter_text = text_file_to_read.read_text(encoding='utf-8')
            # Calculate word count if not available
            if word_count is None and chapter_text:
                word_count = len(chapter_text.split())
        
        # Process chunks
        chunk_metadata_list = merged_chapter_data.get('chunk_metadata', [])
        
        # If chunk_metadata is empty, try to find it in root metadata.json
        if not chunk_metadata_list and root_metadata:
            # Use the same normalization as title matching
            for root_chapter in root_metadata.get('chapters', []):
                root_title = root_chapter.get('title', '')
                # Normalize root title the same way we normalize chapter titles
                root_title_lower = root_title.lower().strip()
                root_title_lower = re.sub(r'\.', '-', root_title_lower)
                root_title_lower = re.sub(r'\b0+(\d)', r'\1', root_title_lower)
                root_title_cleaned = re.sub(r'[^\w\s-]', '', root_title_lower)
                root_title_normalized = re.sub(r'[-\s]+', ' ', root_title_cleaned).strip()
                
                if root_title_normalized == title_normalized:
                    root_chunk_meta = root_chapter.get('chunk_metadata', [])
                    if root_chunk_meta:
                        chunk_metadata_list = root_chunk_meta
                        print(f"    ℹ️  Found chunk metadata in root metadata.json")
                        break
        
        # If no chunk metadata but chunk_count > 0, try to infer from audio files
        if not chunk_metadata_list and merged_chapter_data.get('chunk_count', 0) > 0:
            # Find all chunk audio files for this chapter
            chunk_files = []
            for wav_file in chapters_dir.glob("*_chunk_*.wav"):
                file_base = wav_file.stem.rsplit('_chunk_', 1)[0]
                # Use same normalization as text file matching
                file_title_normalized = file_base.lower().strip()
                file_title_normalized = re.sub(r'\.', '-', file_title_normalized)
                file_title_normalized = re.sub(r'\b0+(\d)', r'\1', file_title_normalized)
                file_title_normalized = re.sub(r'[^\w\s-]', '', file_title_normalized)
                file_title_normalized = re.sub(r'[-\s]+', ' ', file_title_normalized).strip()
                
                if file_title_normalized == title_normalized:
                    match = re.search(r'_chunk_(\d+)\.wav$', wav_file.name)
                    if match:
                        chunk_index = int(match.group(1))
                        chunk_files.append((chunk_index, wav_file))
            
            # Create basic metadata for found chunks
            if chunk_files:
                chunk_files.sort(key=lambda x: x[0])
                chunk_metadata_list = []
                for chunk_index, _ in chunk_files:
                    chunk_metadata_list.append({
                        'index': chunk_index,
                        'text_start': 0,  # Will need to be filled in later
                        'text_end': 0,
                        'status': 'completed' if (chapters_dir / f"{file_base}_chunk_{chunk_index:03d}.wav").exists() else 'pending',
                    })
        
        chunks_dir = chapter_dir / "chunks"
        
        if chunk_metadata_list:
            if not dry_run:
                chunks_dir.mkdir(parents=True, exist_ok=True)
            
            for chunk_meta in chunk_metadata_list:
                chunk_index = chunk_meta.get('index')
                if chunk_index is None:
                    continue
                
                print(f"    🎵 Processing chunk {chunk_index}")
                chunk_dir = chunks_dir / str(chunk_index)
                
                if not dry_run:
                    chunk_dir.mkdir(parents=True, exist_ok=True)
                
                # Move audio file
                # Try different naming patterns - use the actual chapter title from files
                # Find all chunk audio files and match by index
                audio_moved = False
                
                # First try exact chapter title patterns
                audio_patterns = [
                    f"{chapter_title}_chunk_{chunk_index:03d}.wav",
                    f"{chapter_title}_chunk_{chunk_index}.wav",
                ]
                
                for pattern in audio_patterns:
                    old_audio_file = chapters_dir / pattern
                    if old_audio_file.exists():
                        new_audio_file = chunk_dir / "audio.wav"
                        if not dry_run:
                            shutil.copy2(str(old_audio_file), str(new_audio_file))
                        print(f"      ✅ Copied audio file: {old_audio_file.name}")
                        audio_moved = True
                        break
                
                # If not found, search for any file with chunk index using normalized title matching
                if not audio_moved:
                    for wav_file in chapters_dir.glob("*_chunk_*.wav"):
                        # Extract index from filename (e.g., "07-01 - Title_chunk_001.wav" -> 1)
                        match = re.search(r'_chunk_(\d+)\.wav$', wav_file.name)
                        if match and int(match.group(1)) == chunk_index:
                            # Check if it's for this chapter using normalized title matching
                            file_base = wav_file.stem.rsplit('_chunk_', 1)[0]
                            # Use same normalization as text file matching
                            file_title_normalized = file_base.lower().strip()
                            file_title_normalized = re.sub(r'\.', '-', file_title_normalized)
                            file_title_normalized = re.sub(r'\b0+(\d)', r'\1', file_title_normalized)
                            file_title_normalized = re.sub(r'[^\w\s-]', '', file_title_normalized)
                            file_title_normalized = re.sub(r'[-\s]+', ' ', file_title_normalized).strip()
                            
                            if file_title_normalized == title_normalized:
                                new_audio_file = chunk_dir / "audio.wav"
                                if not dry_run:
                                    shutil.copy2(str(wav_file), str(new_audio_file))
                                print(f"      ✅ Copied audio file: {wav_file.name}")
                                audio_moved = True
                                break
                
                if not audio_moved:
                    print(f"      ⚠️  Audio file not found for chunk {chunk_index}")
                
                # Get text positions (default to 0 if not available)
                text_start = chunk_meta.get('text_start', 0)
                text_end = chunk_meta.get('text_end', 0)
                
                # Extract and save chunk text
                if chapter_text is not None and text_end > text_start:
                    chunk_text = chapter_text[text_start:text_end]
                    
                    new_chunk_text_file = chunk_dir / "text.txt"
                    if not dry_run:
                        new_chunk_text_file.write_text(chunk_text, encoding='utf-8')
                    print(f"      ✅ Extracted chunk text ({len(chunk_text)} chars)")
                elif chapter_text is not None and text_end == 0:
                    # If we don't have text positions but have the chapter text,
                    # we can't extract the chunk text accurately
                    print(f"      ⚠️  No text positions available, skipping chunk text extraction")
                
                # Create chunk metadata.json
                chunk_metadata = {
                    'index': chunk_index,
                    'text_start': text_start,
                    'text_end': text_end if text_end > 0 else (len(chapter_text) if chapter_text else 0),
                    'status': chunk_meta.get('status', 'completed' if audio_moved else 'pending'),
                    'generation_time_seconds': chunk_meta.get('generation_time_seconds'),
                    'flagged': chunk_index in merged_chapter_data.get('flagged_chunks', []),
                }
                
                chunk_meta_file = chunk_dir / "metadata.json"
                if not dry_run:
                    with open(chunk_meta_file, 'w', encoding='utf-8') as f:
                        json.dump(chunk_metadata, f, indent=2, ensure_ascii=False)
                print(f"      ✅ Created chunk metadata")
        
        # Create chapter metadata.json
        chapter_metadata = {
            'id': chapter_id,
            'book_id': book_id,
            'chapter_number': chapter_number,  # Extracted or from metadata
            'number': merged_chapter_data.get('number'),  # Royal Road number
            'title': chapter_title,
            'url': merged_chapter_data.get('url'),
            'word_count': word_count,
        }
        
        chapter_meta_file = chapter_dir / "metadata.json"
        if not dry_run:
            with open(chapter_meta_file, 'w', encoding='utf-8') as f:
                json.dump(chapter_metadata, f, indent=2, ensure_ascii=False)
        print(f"    ✅ Created chapter metadata")
        
        chapters_processed.append(merged_chapter_data)
    
    # Update book metadata.json (remove chapter details, keep book-level info)
    new_book_metadata = {
        'book_id': book_metadata.get('book_id'),
        'book_title': book_metadata.get('book_title'),
        'book_url': book_metadata.get('book_url'),
        'filter_book_number': book_metadata.get('filter_book_number'),
    }
    
    output_metadata_path = output_book_dir / "metadata.json"
    if not dry_run:
        with open(output_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(new_book_metadata, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Created book metadata")
    
    print(f"  ✅ Migration complete for {book_dir.name}")


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate audiobook data to nested structure')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--book-dir', type=str, help='Migrate specific book directory (relative to data/books)')
    parser.add_argument('--output-dir', type=str, default='data_tmp', help='Output directory (default: data_tmp)')
    args = parser.parse_args()
    
    # Determine project root (assume script is in scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    books_dir = project_root / "data" / "books"
    output_dir = project_root / args.output_dir / "books"
    
    if not books_dir.exists():
        print(f"❌ Books directory not found: {books_dir}")
        sys.exit(1)
    
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {output_dir}")
    
    if args.book_dir:
        # Migrate specific book
        book_dir = books_dir / args.book_dir
        if not book_dir.exists():
            print(f"❌ Book directory not found: {book_dir}")
            sys.exit(1)
        migrate_book(book_dir, output_dir, dry_run=args.dry_run)
    else:
        # Migrate all books
        print(f"🔍 Scanning for books in: {books_dir}")
        
        book_dirs = [d for d in books_dir.iterdir() if d.is_dir() and (d / "metadata.json").exists()]
        
        if not book_dirs:
            print("  ⚠️  No books found")
            return
        
        print(f"  Found {len(book_dirs)} book(s)")
        
        if args.dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made\n")
        
        for book_dir in book_dirs:
            try:
                migrate_book(book_dir, output_dir, dry_run=args.dry_run)
            except Exception as e:
                print(f"  ❌ Error migrating {book_dir.name}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n✅ Migration complete!")


if __name__ == '__main__':
    main()

