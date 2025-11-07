# Workflow Restructure

## Overview

The application has been restructured to follow a clear, modular workflow where each step is independent and can be triggered separately. All business logic has been moved from scripts into well-structured service classes.

## Architecture

### Service Layer

All business logic is now organized into service classes:

1. **BookService** (`src/services/book_service.py`)
   - Downloads all chapters for a book
   - Manages book metadata

2. **ChapterService** (`src/services/chapter_service.py`)
   - Downloads individual chapters
   - Manages chapter metadata

3. **ChunkingService** (`src/services/chunking_service.py`)
   - Chunks chapter text into segments based on paragraph breaks
   - Creates chunk metadata (positions, sizes, status)
   - Does NOT generate audio - purely text processing

4. **TTSChunkService** (`src/services/tts_service.py`)
   - Generates TTS audio for individual chunks
   - Uses chunk metadata to retrieve text
   - Updates chunk status (pending → running → completed/failed)

### Data Flow

```
1. Download Book Text
   └─> BookService.download_book()
       └─> Creates: data/books/{book_name}/chapters/*.txt
       └─> Updates: metadata.json (chapters list, scraping stats)

2. Download Chapter Text (optional - for individual chapters)
   └─> ChapterService.download_chapter()
       └─> Creates: data/books/{book_name}/chapters/{chapter}.txt
       └─> Updates: metadata.json (chapter entry)

3. Chunk Chapter Text
   └─> ChunkingService.chunk_chapter()
       └─> Reads: chapter text file
       └─> Creates: chunk metadata in metadata.json
       └─> Updates: chapter.chunk_metadata, chapter.chunk_count

4. Generate TTS Audio for Chunks
   └─> TTSChunkService.generate_chunk_audio() or generate_chapter_chunks()
       └─> Reads: chunk metadata from metadata.json
       └─> Reads: chunk text from chapter file using positions
       └─> Creates: data/books/{book_name}/chapters/{chapter}_chunk_{index}.wav
       └─> Updates: chunk.status, chunk.path, chunk.generation_time_seconds
```

## API Endpoints

### Book Operations

- `POST /api/books/download` - Download all chapters for a book
  ```json
  {
    "book_url": "https://royalroad.com/fiction/...",
    "filter_book_number": 7,
    "max_chapters": null
  }
  ```

### Chapter Operations

- `POST /api/chapters/download` - Download a single chapter
  ```json
  {
    "book_id": "book_58187",
    "chapter_url": "https://royalroad.com/fiction/.../chapter/...",
    "chapter_number": 1
  }
  ```

- `POST /api/chapters/chunk` - Chunk a chapter's text
  ```json
  {
    "book_id": "book_58187",
    "chapter_title": "07-01 - The First Cut is the Deepest",
    "chunk_duration_minutes": 1.0,
    "target_chars": null,
    "min_chars": null,
    "max_chars": null
  }
  ```

### Chunk Operations

- `POST /api/chunks/generate` - Generate TTS for multiple chunks
  ```json
  {
    "book_id": "book_58187",
    "chapter_title": "07-01 - The First Cut is the Deepest",
    "chunk_indices": [1, 2, 3],  // null = all pending chunks
    "speaker": null,
    "language": null,
    "speed": null,
    "emotion": null
  }
  ```

- `POST /api/chunks/{chunk_index}/generate` - Generate TTS for a single chunk
  ```
  Query params: book_id, chapter_title, speaker, language, speed, emotion
  ```

## Metadata Structure

### Book Metadata (`metadata.json`)

```json
{
  "book_id": "book_58187",
  "book_title": "Player Manager - A Sports Progression Fantasy - Book 7",
  "book_url": "https://royalroad.com/fiction/...",
  "chapters": [
    {
      "title": "07-01 - The First Cut is the Deepest",
      "scraped": true,
      "scraped_at": "2025-01-27T...",
      "word_count": 12345,
      "is_chunked": true,
      "chunk_count": 14,
      "chunk_metadata": [
        {
          "index": 1,
          "text_start": 0,
          "text_end": 250,
          "text_length": 250,
          "status": "completed",
          "generation_time_seconds": 12.5,
          "path": "data/books/.../chapters/..._chunk_001.wav",
          "created_at": 1234567890.0
        },
        {
          "index": 2,
          "text_start": 250,
          "text_end": 500,
          "text_length": 250,
          "status": "pending",
          "created_at": 1234567890.0
        }
      ],
      "has_audio": true,
      "audio_generated_at": "2025-01-27T..."
    }
  ],
  "scraping": {
    "total_chapters": 50,
    "scraped_chapters": 50,
    "last_scraped": "2025-01-27T..."
  },
  "tts": {
    "total_chapters": 50,
    "generated_chapters": 1,
    "last_generated": "2025-01-27T..."
  },
  "chunks": {
    "total_chunks": 700,
    "chunks_by_chapter": {
      "07-01 - The First Cut is the Deepest": 14
    }
  }
}
```

## Benefits

1. **Separation of Concerns**: Each service has a single, clear responsibility
2. **Modularity**: Services can be used independently or together
3. **Testability**: Each service can be tested in isolation
4. **Flexibility**: UI can trigger any step independently
5. **DRY**: Business logic is centralized, not duplicated in scripts
6. **Maintainability**: Changes to one step don't affect others

## Migration from Scripts

The following scripts have been replaced by services:

- `scripts/scrape_book.py` → `BookService.download_book()`
- `scripts/generate_audio.py` → `TTSChunkService.generate_chapter_chunks()`
- `scripts/regenerate_first_3000.py` → `ChunkingService.chunk_chapter()` + `TTSChunkService.generate_chapter_chunks()`
- `scripts/fix_metadata_for_3000.py` → `ChunkingService.chunk_chapter()`

Scripts can still exist for one-off operations, but core functionality is now in services.

## Next Steps

1. Update UI to show workflow steps:
   - Download book/chapter status
   - Chunking status per chapter
   - TTS generation status per chunk
   - Ability to trigger each step independently

2. Add job queue integration for long-running operations

3. Add progress tracking for chunking and TTS generation

4. Add error handling and retry logic

