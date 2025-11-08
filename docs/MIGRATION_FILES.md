# Files Requiring Migration to New Models & DataSynchronizer

## Summary

This document lists all files that reference the old data access patterns and need to be updated to use the new `DataSynchronizer` and model classes.

## Files by Category

### 🔴 High Priority (Core Functionality)

#### `backend/src/web/book_discovery.py`
**Status:** Critical - Used by API routes  
**Changes:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Update `discover_books()` to use `sync.load_books()`
- Update `discover_chapters()` to use `sync.load_chapters(book_id)`
- Update `get_chapter_audio_urls()` to use `Chapter.chunks_dir` and `Chunk.audio_path`
- Remove direct file globbing (`chapters_dir.glob("*.txt")`)
- Use chapter numbers instead of titles for lookups

**Lines to Update:**
- Line 13: `from src.utils.metadata_tracker import MetadataTracker`
- Line 72-91: `discover_books()` method
- Line 142-210: `discover_chapters()` method
- Line 226-240: `get_chapter_audio_urls()` method

#### `backend/src/web/routes.py`
**Status:** Critical - API endpoints  
**Changes:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Update chunk info endpoint to use chapter numbers
- Update flag chunk endpoint to use `sync.update_chunk_status()`
- Use `Chapter` and `Chunk` models for responses

**Lines to Update:**
- Line 69-199: `get_chunk_info()` endpoint
- Line 516-572: `flag_chunk()` endpoint

### 🟡 Medium Priority (Service Layer)

#### `backend/src/services/book_service.py`
**Status:** Used by API routes  
**Changes:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Update `download_book()` to use `sync.save_book()`
- Update `get_book_info()` to return `Book` model
- Remove manual book directory finding (use `sync.load_book()`)

**Lines to Update:**
- Line 9: `from src.utils.metadata_tracker import MetadataTracker`
- Line 54-72: `download_book()` method
- Line 75-114: `get_book_info()` method

#### `backend/src/services/chapter_service.py`
**Status:** Used by API routes and jobs  
**Changes:**
- Write to new nested structure (`chapters/{chapter_number}/text.txt`)
- Use `DataSynchronizer` to create/update `Chapter` model
- Update `download_chapter()` to save chapter metadata
- Update `get_chapter_info()` to return `Chapter` model

**Lines to Update:**
- Line 9: `from src.utils.metadata_tracker import MetadataTracker`
- Line 46-95: `download_chapter()` method
- Line 97-136: `get_chapter_info()` method

#### `backend/src/services/chunking_service.py`
**Status:** Used by API routes and jobs  
**Changes:**
- Read from new structure (`chapters/{chapter_number}/text.txt`)
- Create `Chunk` models and save via `sync.save_chunk()`
- Extract chunk text and save to `chunks/{index}/text.txt`
- Update chunk metadata in chapter metadata.json

**Lines to Update:**
- Line 9: `from src.utils.metadata_tracker import MetadataTracker`
- Line 45-150: `chunk_chapter()` method
- Line 152-199: `get_chunk_text()` method

#### `backend/src/services/tts_service.py`
**Status:** Used by API routes and jobs  
**Changes:**
- Write audio to new location (`chapters/{chapter_number}/chunks/{index}/audio.wav`)
- Use `sync.load_chunk()` and `sync.save_chunk()` for status updates
- Update chunk status via `sync.update_chunk_status()`

**Lines to Update:**
- Line 11: `from src.utils.metadata_tracker import MetadataTracker`
- Line 43-171: `generate_chunk_audio()` method
- Line 173-273: `generate_chapter_chunks()` method

### 🟢 Lower Priority (Background Jobs & Scraping)

#### `backend/src/web/jobs.py`
**Status:** Background job processing  
**Changes:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Update job handlers to use new structure
- Use models for data access

**Lines to Update:**
- Line 428-524: `_run_chunk_chapter_job()` method
- Line 255-320: `_run_generate_audio_job()` method
- Line 322-350: `_run_generate_chapter_audio_job()` method

#### `backend/src/scraper/royal_road.py`
**Status:** Data ingestion - writes new data  
**Changes:**
- Write to new nested structure (`chapters/{chapter_number}/`)
- Create `Chapter` models and save metadata
- Extract chapter number from title or Royal Road data
- Save chapter text to `chapters/{chapter_number}/text.txt`
- Remove `MetadataTracker` usage

**Lines to Update:**
- Line 19: `from src.utils.metadata_tracker import MetadataTracker`
- Line 400-500: `scrape_book()` method
- Line 473: `tracker.mark_chapter_scraped()` call

#### `backend/src/tts/generator.py`
**Status:** Audio generation  
**Changes:**
- Write to new nested structure
- Use `DataSynchronizer` for chunk updates
- Create chunk directories and save text files

**Lines to Update:**
- Line 14: `from src.utils.metadata_tracker import MetadataTracker`
- Line 120-380: `generate_chapter_chunked()` method

## Migration Checklist

### Phase 1: Read Operations
- [ ] `book_discovery.py` - `discover_books()`
- [ ] `book_discovery.py` - `discover_chapters()`
- [ ] `book_discovery.py` - `get_chapter_audio_urls()`
- [ ] `routes.py` - `get_chunk_info()`

### Phase 2: Service Layer
- [ ] `book_service.py` - `download_book()`
- [ ] `book_service.py` - `get_book_info()`
- [ ] `chapter_service.py` - `download_chapter()`
- [ ] `chapter_service.py` - `get_chapter_info()`
- [ ] `chunking_service.py` - `chunk_chapter()`
- [ ] `chunking_service.py` - `get_chunk_text()`
- [ ] `tts_service.py` - `generate_chunk_audio()`
- [ ] `tts_service.py` - `generate_chapter_chunks()`

### Phase 3: Write Operations
- [ ] `routes.py` - `flag_chunk()`
- [ ] `jobs.py` - All job handlers
- [ ] `scraper/royal_road.py` - `scrape_book()`
- [ ] `tts/generator.py` - `generate_chapter_chunked()`

### Phase 4: Cleanup
- [ ] Mark `MetadataTracker` as deprecated
- [ ] Remove unused imports
- [ ] Update tests
- [ ] Remove `MetadataTracker` class

## Common Patterns to Replace

### Pattern 1: Loading Metadata
```python
# OLD
tracker = MetadataTracker(book_dir)
metadata = tracker.load()
chapter_meta = next((ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title), None)

# NEW
sync = DataSynchronizer(books_dir=settings.books_dir)
book = sync.load_book(book_id)
chapter = sync.load_chapter(book_id, chapter_number)
```

### Pattern 2: File Paths
```python
# OLD
chapters_dir = book_dir / "chapters"
text_file = chapters_dir / f"{chapter_title}.txt"
chunk_file = chapters_dir / f"{chapter_title}_chunk_{index:03d}.wav"

# NEW
chapter = sync.load_chapter(book_id, chapter_number)
text_file = chapter.text_path  # chapters/{number}/text.txt
chunk = sync.load_chunk(book_id, chapter_number, chunk_index)
audio_file = chunk.audio_path  # chapters/{number}/chunks/{index}/audio.wav
```

### Pattern 3: Saving Metadata
```python
# OLD
tracker = MetadataTracker(book_dir)
tracker.mark_chapter_scraped(chapter_title, word_count)
tracker.update_chunk_metadata(chapter_title, chunk_metadata)
tracker.save()

# NEW
sync = DataSynchronizer(books_dir=settings.books_dir)
chapter = Chapter(book_id=book_id, chapter_number=num, title=title, ...)
sync.save_chapter(chapter)
chunk = Chunk(index=idx, book_id=book_id, text_start=start, text_end=end, ...)
sync.save_chunk(chunk)
```

### Pattern 4: Finding Book Directory
```python
# OLD
book_dir = None
for dir_path in settings.books_dir.iterdir():
    if dir_path.is_dir() and book_id in dir_path.name:
        metadata_path = dir_path / "metadata.json"
        if metadata_path.exists():
            # ... check metadata ...
            book_dir = dir_path
            break

# NEW
sync = DataSynchronizer(books_dir=settings.books_dir)
book = sync.load_book(book_id)
if book and book.path:
    book_dir = Path(book.path)
```

## Notes

- All chapter numbers should be zero-padded (01, 02, etc.) for directory names
- Chapter IDs follow format: `{book_id}_{chapter_number}` (e.g., `book_58187_01`)
- Chunk indices are 1-based
- All timestamps use Unix epoch (float)
- Status uses `ChunkStatus` enum
- Use model properties for file paths instead of manual construction

