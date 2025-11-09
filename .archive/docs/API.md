# API Reference

> **Status:** Current  
> **Last Updated:** 2025-01-27

## Endpoints

### Health Check

```
GET /api/health
```

Returns system health status.

**Response:**
```json
{
  "status": "ok"
}
```

### Books

#### List Books

```
GET /api/books
```

Returns list of all downloaded books.

**Response:**
```json
{
  "books": [
    {
      "id": "book_58187",
      "title": "Player Manager - A Sports Progression Fantasy - Book 7",
      "author": "Ted Steele",
      "chapter_count": 16,
      "scraped_count": 16,
      "has_audio": true,
      "audio_chapter_count": 1
    }
  ]
}
```

#### Get Book Preview

```
GET /api/books/preview?book_url={url}&book_number={number}
```

Get preview information for a book from Royal Road (before downloading).

**Response:**
```json
{
  "chapter_count": 50,
  "chapters": ["Chapter 1", "Chapter 2", ...],
  "preview_text": "First 500 characters of first chapter..."
}
```

#### Get Book

```
GET /api/books/{book_id}
```

Returns details for a specific book including chapters.

**Response:**
```json
{
  "id": "book_58187",
  "title": "Player Manager - A Sports Progression Fantasy - Book 7",
  "chapters": [
    {
      "title": "07-01 - The First Cut is the Deepest",
      "number": 1,
      "scraped": true,
      "has_audio": true,
      "is_chunked": true,
      "chunk_count": 23
    }
  ]
}
```

### Chapters

#### List Chapters

```
GET /api/books/{book_id}/chapters
```

Returns list of chapters for a book.

**Response:**
```json
{
  "chapters": [
    {
      "title": "07-01 - The First Cut is the Deepest",
      "number": 1,
      "scraped": true,
      "has_audio": true,
      "is_chunked": true,
      "chunk_count": 23
    }
  ]
}
```

#### Get Chapter

```
GET /api/books/{book_id}/chapters/{chapter_number}
```

Returns chapter details and audio URLs (for chunked audio).

**Response:**
```json
{
  "title": "07-01 - The First Cut is the Deepest",
  "number": 1,
  "audio_urls": [
    "/static/audio/.../chunk_001.wav",
    "/static/audio/.../chunk_002.wav"
  ],
  "is_chunked": true,
  "chunk_count": 23
}
```

#### Get Chunk Metadata

```
GET /api/books/{book_id}/chapters/{chapter_title}/chunks
```

Returns detailed chunk information including text positions and status.

**Response:**
```json
{
  "chunks": [
    {
      "index": 1,
      "text_start": 0,
      "text_end": 500,
      "status": "completed",
      "generation_time_seconds": 45.2,
      "created_at": "2025-01-27T12:00:00Z"
    }
  ],
  "total_text_length": 77118
}
```

### Jobs

#### List Jobs

```
GET /api/jobs?book_id={book_id}
```

Returns list of background jobs (scraping, audio generation).

**Response:**
```json
{
  "jobs": [
    {
      "id": "job_123",
      "type": "generate_audio",
      "status": "running",
      "book_id": "book_58187",
      "chapter_title": "07-01 - The First Cut is the Deepest",
      "message": "Generating chunk 5 of 23...",
      "created_at": "2025-01-27T12:00:00Z"
    }
  ]
}
```

#### Get Job

```
GET /api/jobs/{job_id}
```

Returns details for a specific job.

#### Create Scraping Job

```
POST /api/jobs/scrape
```

**Request:**
```json
{
  "book_url": "https://www.royalroad.com/fiction/...",
  "filter_book_number": 7,
  "max_chapters": null
}
```

#### Create Audio Generation Job

```
POST /api/jobs/generate-audio
```

**Request:**
```json
{
  "book_id": "book_58187",
  "chapter_title": "07-01 - The First Cut is the Deepest",
  "speaker": "british_male"
}
```

#### Create Chunk Generation Job

```
POST /api/jobs/generate-chunk
```

**Request:**
```json
{
  "book_id": "book_58187",
  "chapter_title": "07-01 - The First Cut is the Deepest",
  "chunk_index": 5,
  "speaker": "british_male"
}
```

#### Cancel Job

```
POST /api/jobs/{job_id}/cancel
```

### Series

#### Get Series Books

```
GET /api/books/{book_id}/series
```

Returns list of books in the same series (from Royal Road).

**Response:**
```json
{
  "books": [
    {
      "book_number": 7,
      "title": "Player Manager Book 7",
      "in_system": true,
      "has_audio": true
    }
  ]
}
```

### Search

#### Search Royal Road

```
GET /api/search?q={query}
```

Search Royal Road for books.

**Response:**
```json
{
  "results": [
    {
      "title": "Player Manager",
      "url": "https://www.royalroad.com/fiction/...",
      "author": "Ted Steele"
    }
  ]
}
```

### Progress

#### Get Progress

```
GET /api/progress/{book_id}
```

Returns playback progress for a book (from database).

**Response:**
```json
{
  "book_id": "book_58187",
  "current_chapter": 1,
  "position_seconds": 1200.0
}
```

#### Update Progress

```
POST /api/progress
```

**Request:**
```json
{
  "book_id": "book_58187",
  "chapter_number": 1,
  "position_seconds": 1200.0
}
```

### Chunks

#### Flag Chunk

```
POST /api/books/{book_id}/chapters/{chapter_title}/chunks/{chunk_index}/flag
```

Flag a chunk for reprocessing (marks as flagged in metadata).

**Response:**
```json
{
  "status": "flagged"
}
```

## Notes

- All chapter titles in URLs are URL-encoded
- Chunked audio uses sequential `.wav` files (one per chunk)
- Job status updates are polled by frontend (1-3 second intervals)
- Metadata is stored in JSON files alongside book data
- Progress is stored in SQLite database
