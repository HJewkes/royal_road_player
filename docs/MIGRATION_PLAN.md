# Migration Plan: Old Data Access → New Models, Controllers & DataSynchronizer

## Overview

This document outlines the plan to migrate from the old `MetadataTracker`-based data access pattern to the new architecture:
- **Models**: Data classes with business logic accessors (`Book`, `Chapter`, `Chunk`)
- **Controllers**: Single-responsibility controllers for operations (`BookController`, `ChapterController`, `ChunkController`, `ChunkingController`, `TTSController`)
- **DataSynchronizer**: Persistence layer for loading/saving models to filesystem

## Current State vs Target State

### Old Structure
```
data/books/{book_id}/
├── metadata.json (flat structure with chapters array)
└── chapters/
    ├── {chapter_title}.txt
    ├── {chapter_title}_chunk_001.wav
    ├── {chapter_title}_chunk_002.wav
    └── ...
```

### New Structure
```
data/books/{book_id}/
├── metadata.json (book-level metadata)
└── chapters/
    └── {chapter_number}/  (e.g., "01", "02")
        ├── metadata.json (chapter-level metadata)
        ├── text.txt
        └── chunks/
            └── {index}/  (e.g., "1", "2")
                ├── metadata.json (chunk-level metadata)
                ├── text.txt
                └── audio.wav
```

## Migration Strategy

### Phase 1: Core Infrastructure Updates

#### 1.1 Update `book_discovery.py`
**Current Issues:**
- Uses `MetadataTracker` to load book metadata
- Direct file globbing for chapters (`chapters_dir.glob("*.txt")`)
- Assumes old flat structure

**Changes Needed:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Use `sync.load_books()` instead of manual directory scanning
- Use `sync.load_chapters(book_id)` instead of globbing
- Update chapter discovery to use chapter numbers instead of titles
- Update audio file discovery to use new nested paths

**Key Methods to Update:**
- `discover_books()` → Use `DataSynchronizer.load_books()`
- `discover_chapters()` → Use `DataSynchronizer.load_chapters()`
- `get_chapter_audio_urls()` → Use `Chapter.chunks_dir` and `Chunk.audio_path`

#### 1.2 Update `routes.py`
**Current Issues:**
- Uses `MetadataTracker` for chunk metadata
- Direct file path construction (`chapters_dir / f"{chapter_title}.txt"`)
- Old chunk file naming pattern (`{chapter_title}_chunk_{index}.wav`)

**Changes Needed:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Use `Chapter` and `Chunk` models
- Update chunk info endpoint to use `sync.load_chunks()`
- Update flag chunk endpoint to use `sync.update_chunk_status()`

**Key Endpoints to Update:**
- `GET /api/books/{book_id}/chapters/{chapter_title}/chunks` → Use chapter_number
- `POST /api/books/{book_id}/chapters/{chapter_title}/chunks/{chunk_index}/flag` → Use chapter_number

### Phase 2: Service Layer Updates

#### 2.1 Update `book_service.py`
**Current Issues:**
- Uses `MetadataTracker` for metadata refresh
- Manual book directory finding

**Changes Needed:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Use `sync.load_book()` and `sync.save_book()`
- Update `get_book_info()` to return `Book` model

**Methods to Update:**
- `download_book()` → Use `sync.save_book()` after scraping
- `get_book_info()` → Return `Book` model with computed stats

#### 2.2 Update `chapter_service.py`
**Current Issues:**
- Writes to old flat structure (`chapters/{chapter_title}.txt`)
- Uses `MetadataTracker.mark_chapter_scraped()`
- Manual file path construction

**Changes Needed:**
- Write to new nested structure (`chapters/{chapter_number}/text.txt`)
- Use `DataSynchronizer` to create/update `Chapter` model
- Update `download_chapter()` to save chapter metadata
- Update `get_chapter_info()` to return `Chapter` model

**Methods to Update:**
- `download_chapter()` → Create `Chapter` model and save via `sync.save_chapter()`
- `get_chapter_info()` → Return `Chapter` model with computed properties
- `find_book_dir()` → Can be replaced with `sync.load_book()`

#### 2.3 Update `chunking_service.py`
**Current Issues:**
- Reads from old structure (`chapters/{chapter_title}.txt`)
- Writes chunk metadata via `MetadataTracker.update_chunk_metadata()`
- Creates chunk metadata dicts manually

**Changes Needed:**
- Read from new structure (`chapters/{chapter_number}/text.txt`)
- Create `Chunk` models and save via `sync.save_chunk()`
- Extract chunk text and save to `chunks/{index}/text.txt`
- Update chunk metadata in chapter metadata.json

**Methods to Update:**
- `chunk_chapter()` → Create `Chunk` models, save text files, update metadata
- `get_chunk_text()` → Read from `Chunk.text_path`

#### 2.4 Update `tts_service.py`
**Current Issues:**
- Writes audio to old location (`chapters/{chapter_title}_chunk_{index}.wav`)
- Updates chunk metadata via `MetadataTracker`
- Manual file path construction

**Changes Needed:**
- Write audio to new location (`chapters/{chapter_number}/chunks/{index}/audio.wav`)
- Use `sync.load_chunk()` and `sync.save_chunk()` for status updates
- Update chunk status via `sync.update_chunk_status()`

**Methods to Update:**
- `generate_chunk_audio()` → Use `Chunk.audio_path`, update via `sync.save_chunk()`
- `generate_chapter_chunks()` → Load chunks via `sync.load_chunks()`

### Phase 3: Background Jobs & Scraping

#### 3.1 Update `jobs.py`
**Current Issues:**
- Uses `MetadataTracker` for chunk metadata updates
- Assumes old file structure
- Manual file globbing

**Changes Needed:**
- Replace `MetadataTracker` with `DataSynchronizer`
- Update job handlers to use new structure
- Use models for data access

**Job Types to Update:**
- `GENERATE_AUDIO` → Use `sync.load_chapters()` and new paths
- `GENERATE_CHAPTER_AUDIO` → Use `Chapter` model
- `GENERATE_CHUNK_AUDIO` → Use `Chunk` model
- `CHUNK_CHAPTER` → Use `ChunkingService` (already updated)

#### 3.2 Update `scraper/royal_road.py`
**Current Issues:**
- Writes to old flat structure
- Uses `MetadataTracker` for metadata updates
- Creates chapter files with title-based names

**Changes Needed:**
- Write to new nested structure (`chapters/{chapter_number}/`)
- Create `Chapter` models and save metadata
- Extract chapter number from title or Royal Road data
- Save chapter text to `chapters/{chapter_number}/text.txt`

**Methods to Update:**
- `scrape_book()` → Create nested structure, save `Chapter` models
- `scrape_chapter()` → Return chapter number, save to nested structure
- Remove `MetadataTracker` usage, use `DataSynchronizer` instead

#### 3.3 Update `tts/generator.py`
**Current Issues:**
- Writes to old structure
- Uses `MetadataTracker` for chunk metadata

**Changes Needed:**
- Write to new nested structure
- Use `DataSynchronizer` for chunk updates
- Create chunk directories and save text files

**Methods to Update:**
- `generate_chapter_chunked()` → Use new structure, `DataSynchronizer`

### Phase 4: Cleanup & Deprecation

#### 4.1 Mark `MetadataTracker` as Deprecated
- Add deprecation warnings
- Keep for backward compatibility during migration
- Document migration path

#### 4.2 Remove Old Code Paths
- After all code is migrated, remove `MetadataTracker`
- Remove old file structure handling code
- Update tests

## Implementation Order

1. **Start with read-only operations** (book_discovery, routes)
   - Lower risk, easier to test
   - Establishes patterns for other code

2. **Update service layer** (book_service, chapter_service)
   - Core business logic
   - Used by multiple consumers

3. **Update write operations** (chunking_service, tts_service)
   - More complex, needs careful testing
   - Affects data generation

4. **Update background jobs** (jobs.py)
   - Depends on services being updated
   - Can run in parallel with other work

5. **Update scrapers** (royal_road.py, generator.py)
   - Data ingestion points
   - Critical for new data creation

6. **Cleanup** (deprecate MetadataTracker)
   - Final step after all migration complete

## Key Patterns to Follow

### Loading Data
```python
# OLD
tracker = MetadataTracker(book_dir)
metadata = tracker.load()
chapter_meta = next((ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title), None)

# NEW - Using Controllers
book_ctrl = BookController()
book = book_ctrl.get_book(book_id)
chapter_ctrl = ChapterController()
chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
chunks = chapter_ctrl.get_chunks(book_id, chapter_number)
```

### Saving Data
```python
# OLD
tracker = MetadataTracker(book_dir)
tracker.mark_chapter_scraped(chapter_title, word_count)
tracker.update_chunk_metadata(chapter_title, chunk_metadata)
tracker.save()

# NEW - Using Controllers
chapter_ctrl = ChapterController()
chapter = Chapter(book_id=book_id, chapter_number=num, title=title, ...)
chapter_ctrl.save_chapter(chapter)

chunk_ctrl = ChunkController()
chunk = Chunk(index=idx, book_id=book_id, text_start=start, text_end=end, ...)
chunk_ctrl.save_chunk(chunk)
```

### File Paths
```python
# OLD
text_file = chapters_dir / f"{chapter_title}.txt"
chunk_file = chapters_dir / f"{chapter_title}_chunk_{index:03d}.wav"

# NEW - Using Model Accessors
chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
text_file = chapter.text_path  # chapters/{number}/text.txt
has_text = chapter.has_text  # Check if text exists
word_count = chapter.word_count  # Get word count

chunk = chunk_ctrl.get_chunk(book_id, chapter_number, chunk_index)
audio_file = chunk.audio_path  # chapters/{number}/chunks/{index}/audio.wav
has_audio = chunk.has_audio  # Check if audio exists
is_completed = chunk.is_completed  # Check completion status
```

### Business Logic Operations
```python
# OLD
tracker = MetadataTracker(book_dir)
metadata = tracker.load()
chunk_count = chapter_meta.get('chunk_count', 0)
has_audio = chapter_meta.get('has_audio', False)

# NEW - Using Model Accessors
chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
chunk_count = chapter.chunk_count  # Computed from filesystem
has_audio = chapter.has_audio  # Computed from filesystem
is_chunked = chapter.is_chunked  # Computed from filesystem
word_count = chapter.word_count  # Computed from text file
```

### Complex Operations
```python
# OLD
service = ChunkingService()
result = service.chunk_chapter(book_id, chapter_title, ...)

# NEW - Using Controllers
chunking_ctrl = ChunkingController()
result = chunking_ctrl.chunk_chapter(book_id, chapter_number, ...)

# OLD
service = TTSChunkService()
result = service.generate_chunk_audio(book_id, chapter_title, chunk_index, ...)

# NEW - Using Controllers
tts_ctrl = TTSController()
result = tts_ctrl.generate_chunk_audio(book_id, chapter_number, chunk_index, ...)
```

### Chapter Number Resolution
- Prefer `chapter_number` from metadata
- Fall back to Royal Road `number`
- Extract from title as last resort
- Use zero-padded format (e.g., "01", "02") for directory names

## Testing Strategy

1. **Unit Tests**
   - Test each service method with new models
   - Verify DataSynchronizer operations
   - Test model property accessors

2. **Integration Tests**
   - Test full workflows (download → chunk → generate)
   - Verify filesystem structure matches models
   - Test metadata consistency

3. **Migration Tests**
   - Verify old data can be read (if needed)
   - Test new data creation
   - Ensure no data loss

## Risk Mitigation

1. **Incremental Migration**
   - Update one module at a time
   - Keep old code working during transition
   - Test thoroughly before moving to next module

2. **Backward Compatibility**
   - Keep `MetadataTracker` during migration
   - Add compatibility layer if needed
   - Document breaking changes

3. **Data Validation**
   - Verify all existing data accessible
   - Test new data creation
   - Check metadata consistency

4. **Rollback Plan**
   - Keep old code in git history
   - Can revert individual modules if issues found
   - Test rollback procedure

## Success Criteria

- [ ] All code uses `DataSynchronizer` instead of `MetadataTracker`
- [ ] All file operations use new nested structure
- [ ] All models (`Book`, `Chapter`, `Chunk`) are used consistently
- [ ] No direct file path construction (use model properties)
- [ ] All tests pass
- [ ] Existing data remains accessible
- [ ] New data created in correct structure
- [ ] `MetadataTracker` marked as deprecated
- [ ] Documentation updated

## Notes

- Chapter numbers should be zero-padded (01, 02, etc.) for directory names
- Chapter IDs follow format: `{book_id}_{chapter_number}` (e.g., `book_58187_01`)
- Chunk indices are 1-based
- All timestamps use Unix epoch (float)
- Status uses `ChunkStatus` enum

