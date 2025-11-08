# Architecture: Models, Controllers, and Data Synchronization

## Overview

This document describes the architecture for business logic separation using models with accessors and single-responsibility controllers.

## Architecture Principles

### 1. Models (Data + Accessors)
Models contain:
- **Data fields**: Core attributes of the entity
- **Path accessors**: Properties that return file paths (`text_path`, `audio_path`, etc.)
- **Business logic accessors**: Computed properties based on the model's state and filesystem

### 2. Controllers (Operations)
Controllers handle:
- **Single-object operations**: Loading, saving, updating individual objects
- **Multi-object operations**: Operations involving multiple objects (e.g., chunking a chapter)
- **Business logic operations**: Complex operations that modify state

### 3. Data Synchronizer (Persistence)
`DataSynchronizer` handles:
- **Loading**: Reading from filesystem → models
- **Saving**: Writing models → filesystem
- **Synchronization**: Keeping models and filesystem in sync

## Model Accessors

### Book Model
```python
@property
def has_chapters_dir(self) -> bool  # Check if chapters directory exists
@property
def chapter_count(self) -> int      # Count chapter directories
```

### Chapter Model
```python
@property
def has_text(self) -> bool          # Check if text file exists
@property
def word_count(self) -> Optional[int]  # Count words in text
@property
def has_chunks_dir(self) -> bool    # Check if chunks directory exists
@property
def chunk_count(self) -> int        # Count chunk directories
@property
def is_chunked(self) -> bool        # Check if chapter is chunked
@property
def has_audio(self) -> bool         # Check if chapter has audio files
```

### Chunk Model
```python
@property
def has_text(self) -> bool          # Check if text file exists
@property
def has_audio(self) -> bool         # Check if audio file exists
@property
def is_completed(self) -> bool       # Check if chunk is completed
@property
def is_pending(self) -> bool         # Check if chunk is pending
@property
def is_failed(self) -> bool          # Check if chunk failed
@property
def is_flagged(self) -> bool         # Check if chunk is flagged
```

## Controllers

### BookController
**Responsibility**: Book-level operations

**Methods**:
- `get_book(book_id)` - Get a book by ID
- `list_books()` - List all books
- `get_chapters(book_id)` - Get all chapters for a book
- `get_book_stats(book_id)` - Compute book statistics
- `save_book(book)` - Save book to filesystem

**Use Cases**:
- Loading books and chapters
- Computing book-level statistics
- Book discovery

### ChapterController
**Responsibility**: Chapter-level operations

**Methods**:
- `get_chapter(book_id, chapter_number)` - Get a chapter
- `get_chunks(book_id, chapter_number)` - Get all chunks for a chapter
- `get_chapter_stats(book_id, chapter_number)` - Compute chapter statistics
- `save_chapter(chapter)` - Save chapter to filesystem
- `get_chapter_text(book_id, chapter_number)` - Get chapter text content

**Use Cases**:
- Loading chapters and chunks
- Computing chapter-level statistics
- Reading chapter text

### ChunkController
**Responsibility**: Chunk-level operations

**Methods**:
- `get_chunk(book_id, chapter_number, chunk_index)` - Get a chunk
- `get_chunk_text(book_id, chapter_number, chunk_index)` - Get chunk text
- `update_status(book_id, chapter_number, chunk_index, status)` - Update chunk status
- `flag_chunk(book_id, chapter_number, chunk_index, flagged)` - Flag/unflag chunk
- `save_chunk(chunk)` - Save chunk to filesystem

**Use Cases**:
- Loading individual chunks
- Updating chunk status
- Flagging chunks for reprocessing

### ChunkingController
**Responsibility**: Multi-chunk operations (chunking a chapter)

**Methods**:
- `chunk_chapter(book_id, chapter_number, ...)` - Chunk a chapter into segments

**Use Cases**:
- Creating chunks from chapter text
- Saving chunk text files
- Initializing chunk metadata

### TTSController
**Responsibility**: Audio generation operations

**Methods**:
- `generate_chunk_audio(...)` - Generate audio for a single chunk
- `generate_chapter_chunks(...)` - Generate audio for multiple chunks

**Use Cases**:
- Generating TTS audio for chunks
- Updating chunk status during generation
- Handling audio generation errors

## Usage Examples

### Example 1: Check if chapter has audio
```python
# OLD WAY (scattered logic)
chapters_dir = book_dir / "chapters"
audio_files = list(chapters_dir.glob(f"{chapter_title}*.wav"))
has_audio = len(audio_files) > 0

# NEW WAY (model accessor)
chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
has_audio = chapter.has_audio
```

### Example 2: Get chapter statistics
```python
# OLD WAY (manual computation)
tracker = MetadataTracker(book_dir)
metadata = tracker.load()
chapter_meta = next((ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title), {})
chunk_count = chapter_meta.get('chunk_count', 0)
has_audio = chapter_meta.get('has_audio', False)

# NEW WAY (controller method)
stats = chapter_ctrl.get_chapter_stats(book_id, chapter_number)
chunk_count = stats['chunk_count']
has_audio = stats['has_audio']
```

### Example 3: Chunk a chapter
```python
# OLD WAY (service with mixed responsibilities)
service = ChunkingService()
result = service.chunk_chapter(book_id, chapter_title, ...)

# NEW WAY (single-responsibility controller)
controller = ChunkingController()
result = controller.chunk_chapter(book_id, chapter_number, ...)
```

### Example 4: Generate audio for chunks
```python
# OLD WAY (service with mixed responsibilities)
service = TTSChunkService()
result = service.generate_chapter_chunks(book_id, chapter_title, ...)

# NEW WAY (single-responsibility controller)
controller = TTSController()
result = controller.generate_chapter_chunks(book_id, chapter_number, ...)
```

## Benefits

1. **Separation of Concerns**
   - Models: Data + computed properties
   - Controllers: Operations + business logic
   - DataSynchronizer: Persistence

2. **Single Responsibility**
   - Each controller has one clear purpose
   - Models contain only data and accessors
   - No mixed responsibilities

3. **Testability**
   - Models can be tested independently
   - Controllers can be mocked easily
   - Clear interfaces for testing

4. **Maintainability**
   - Business logic is centralized
   - Changes are localized
   - Easy to understand and modify

5. **Reusability**
   - Controllers can be used by services, routes, jobs
   - Models provide consistent accessors
   - No code duplication

## Migration Path

When migrating old code:

1. **Replace direct file access** → Use model accessors
   ```python
   # OLD
   text_file = chapters_dir / f"{chapter_title}.txt"
   
   # NEW
   chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
   text_file = chapter.text_path
   ```

2. **Replace MetadataTracker** → Use controllers
   ```python
   # OLD
   tracker = MetadataTracker(book_dir)
   metadata = tracker.load()
   
   # NEW
   book_ctrl = BookController()
   book = book_ctrl.get_book(book_id)
   ```

3. **Replace service methods** → Use controller methods
   ```python
   # OLD
   service = ChunkingService()
   service.chunk_chapter(...)
   
   # NEW
   controller = ChunkingController()
   controller.chunk_chapter(...)
   ```

## File Structure

```
backend/src/
├── models/              # Data models with accessors
│   ├── book.py
│   ├── chapter.py
│   ├── chunk.py
│   └── enums.py
├── controllers/         # Single-responsibility controllers
│   ├── book_controller.py
│   ├── chapter_controller.py
│   ├── chunk_controller.py
│   ├── chunking_controller.py
│   └── tts_controller.py
├── data/               # Data persistence
│   └── data_synchronizer.py
└── services/           # (Legacy - to be migrated)
    └── ...
```

