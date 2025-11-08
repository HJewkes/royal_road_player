# Migration Status: MetadataTracker → Controllers

## ✅ Completed

### Services Layer
- [x] **BookService** - Now uses `BookController`
- [x] **ChapterService** - Now uses `ChapterController` and new nested structure
- [x] **ChunkingService** - Now uses `ChunkingController`
- [x] **TTSChunkService** - Now uses `TTSController`

### Models
- [x] **Book** - Enhanced with business logic accessors
- [x] **Chapter** - Enhanced with business logic accessors
- [x] **Chunk** - Enhanced with business logic accessors

### Controllers
- [x] **BookController** - Book-level operations
- [x] **ChapterController** - Chapter-level operations
- [x] **ChunkController** - Chunk-level operations
- [x] **ChunkingController** - Chunking operations
- [x] **TTSController** - TTS audio generation

### Data Layer
- [x] **DataSynchronizer** - Persistence layer for models

## ⚠️ In Progress / Pending

### Deprecated (Still Used)
- [x] **MetadataTracker** - Marked as deprecated with warnings
  - Still used in: `routes.py`, `book_discovery.py`, `scraper/royal_road.py`, `jobs.py`, `tts/generator.py`
  - These files need migration to use controllers

### Files Needing Migration

#### High Priority
1. **`backend/src/web/book_discovery.py`**
   - Uses `MetadataTracker` for book/chapter discovery
   - Should use `BookController` and `ChapterController`
   - Status: Needs migration

2. **`backend/src/web/routes.py`**
   - Uses `MetadataTracker` for chunk info and flagging
   - Should use `ChapterController` and `ChunkController`
   - Status: Needs migration

#### Medium Priority
3. **`backend/src/web/jobs.py`**
   - Uses `MetadataTracker` in job handlers
   - Should use controllers
   - Status: Needs migration

4. **`backend/src/scraper/royal_road.py`**
   - Uses `MetadataTracker` when scraping books
   - Should use `ChapterController` to save chapters
   - Status: Needs migration

5. **`backend/src/tts/generator.py`**
   - Uses `MetadataTracker` for chunk metadata
   - Should use `TTSController` and `ChunkController`
   - Status: Needs migration

## Migration Notes

### Breaking Changes
- Services now use `chapter_number` instead of `chapter_title` for lookups
- Chapter numbers are zero-padded (e.g., `01`, `02`) for directory names
- File structure changed to nested format

### Compatibility
- `MetadataTracker` is deprecated but still functional
- Old code will work but show deprecation warnings
- New code should use controllers

## Next Steps

1. Migrate `book_discovery.py` to use controllers
2. Migrate `routes.py` to use controllers
3. Migrate `jobs.py` to use controllers
4. Migrate `scraper/royal_road.py` to use new structure
5. Migrate `tts/generator.py` to use controllers
6. Remove `MetadataTracker` class entirely

