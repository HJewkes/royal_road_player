# DataSynchronizer Usage Analysis

> **Generated:** 2025-01-27  
> **Status:** Current Usage Map

## Overview

`DataSynchronizer` is still being used as a **hybrid persistence layer** that bridges between the database and filesystem. It attempts to load from the database first, then falls back to filesystem for backward compatibility.

## Current Usage Locations

### 1. **Controllers** (Primary Usage)

All controllers use `DataSynchronizer` as their data access layer:

#### `BookController` (`backend/src/controllers/book_controller.py`)
- `self.sync.load_book()` - Load single book
- `self.sync.load_books()` - Load all books
- `self.sync.load_chapters()` - Load chapters for a book
- `self.sync.save_book()` - Save book to filesystem

#### `ChapterController` (`backend/src/controllers/chapter_controller.py`)
- `self.sync.load_chapter()` - Load single chapter
- `self.sync.load_chunks()` - Load chunks for a chapter
- `self.sync.save_chapter()` - Save chapter to filesystem

#### `ChunkController` (`backend/src/controllers/chunk_controller.py`)
- `self.sync.load_chunk()` - Load single chunk
- `self.sync.update_chunk_status()` - Update chunk status
- `self.sync.save_chunk()` - Save chunk to filesystem

#### `ChunkingController` (`backend/src/controllers/chunking_controller.py`)
- `self.sync.save_chunk()` - Save chunks after chunking
- `self.sync.load_chapter()` - Load chapter for rechunking
- `self.sync.load_chunks()` - Load existing chunks

#### `TTSController` (`backend/src/controllers/tts_controller.py`)
- `self.sync.load_chunk()` - Load chunk for audio generation
- `self.sync.update_chunk_status()` - Update chunk status during processing
- `self.sync.save_chunk()` - Save completed chunk
- `self.sync.load_chunks()` - Load chunks for batch operations

### 2. **Services**

#### `job_queue.py` (`backend/src/services/job_queue.py`)
- `sync.load_chunks()` - Load chunks for enqueueing (line 205)
- `sync.load_chunk()` - Load chunk for recovery check (line 318)

## DataSynchronizer's Current Role

Looking at `data_synchronizer.py`, it acts as a **hybrid adapter**:

1. **Load Operations:**
   - Tries database first (`BookRepository`, `ChapterRepository`, `ChunkRepository`)
   - Falls back to filesystem if database is empty or fails
   - Returns domain models (`Book`, `Chapter`, `Chunk`)

2. **Save Operations:**
   - Saves to filesystem (JSON metadata files)
   - **Note:** May also save to database (needs verification)

## Migration Path Considerations

### Why DataSynchronizer Still Exists

1. **Backward Compatibility:** Filesystem data still exists and needs to be accessible
2. **Migration Support:** Allows gradual migration from filesystem to database
3. **Fallback Safety:** If database fails, filesystem is still available
4. **File Operations:** Some operations (like reading text files) are filesystem-specific

### Potential Issues

1. **Dual Storage:** Data may exist in both database and filesystem, causing sync issues
2. **Performance:** Filesystem operations are slower than database queries
3. **Complexity:** Two persistence layers add complexity
4. **Inconsistency Risk:** Database and filesystem can get out of sync

## Recommendations

### Option 1: Keep DataSynchronizer as Adapter (Current Approach)
**Pros:**
- Backward compatible
- Safe fallback
- Gradual migration possible

**Cons:**
- Dual storage complexity
- Potential sync issues
- Slower than pure database

### Option 2: Migrate Controllers to Use Repositories Directly
**Pros:**
- Single source of truth (database)
- Faster performance
- Simpler architecture
- Better consistency

**Cons:**
- Requires migration of existing filesystem data
- Need to handle filesystem operations separately (text file reading, etc.)
- Breaking change for any code expecting filesystem fallback

### Option 3: Hybrid Approach - Repositories + File Operations
**Pros:**
- Repositories for metadata/queries
- Direct file operations for text/audio files
- Clear separation of concerns

**Cons:**
- More refactoring required
- Need to ensure file paths are stored in database

## Files That Need Refactoring (If Migrating)

If moving away from DataSynchronizer:

1. **Controllers:**
   - `book_controller.py` - Replace `self.sync.*` with repository calls
   - `chapter_controller.py` - Replace `self.sync.*` with repository calls
   - `chunk_controller.py` - Replace `self.sync.*` with repository calls
   - `chunking_controller.py` - Replace `self.sync.*` with repository calls
   - `tts_controller.py` - Replace `self.sync.*` with repository calls

2. **Services:**
   - `job_queue.py` - Replace `sync.load_chunks()` and `sync.load_chunk()` with repository calls

3. **File Operations:**
   - Text file reading (currently done via `Chapter.text_path`)
   - Audio file paths (currently done via `Chunk.audio_path`)
   - These would need to be handled separately or via repository methods

## Current State Summary

- **Database:** Used for queries, counts, status updates (via repositories)
- **DataSynchronizer:** Used for loading domain models (Book/Chapter/Chunk) with database fallback
- **Filesystem:** Still primary storage for text files, audio files, and metadata JSON files

## Next Steps

1. **Decide on architecture:** Keep hybrid or migrate to pure database?
2. **If migrating:** Create migration plan for filesystem → database
3. **If keeping:** Document the dual-storage pattern and sync strategy
4. **File operations:** Determine how to handle text/audio file access without DataSynchronizer

