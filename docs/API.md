# API Reference

> **Status:** Draft  
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
      "id": "book_12345",
      "title": "Book Title",
      "author": "Author Name",
      "chapter_count": 50,
      "created_at": "2025-01-27T00:00:00Z"
    }
  ]
}
```

#### Get Book

```
GET /api/books/{book_id}
```

Returns details for a specific book.

**Response:**
```json
{
  "id": "book_12345",
  "title": "Book Title",
  "author": "Author Name",
  "chapters": [...]
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
      "id": 1,
      "chapter_number": 1,
      "title": "Chapter 1",
      "has_audio": true,
      "duration_seconds": 3600.0
    }
  ]
}
```

#### Get Chapter

```
GET /api/chapters/{chapter_id}
```

Returns chapter details and audio URL.

**Response:**
```json
{
  "id": 1,
  "book_id": "book_12345",
  "title": "Chapter 1",
  "audio_url": "/static/audio/book_12345/chapter_1.mp3",
  "duration_seconds": 3600.0
}
```

### Progress

#### Get Progress

```
GET /api/progress/{book_id}
```

Returns playback progress for a book.

**Response:**
```json
{
  "book_id": "book_12345",
  "current_chapter": 5,
  "position_seconds": 1200.0
}
```

#### Update Progress

```
POST /api/progress
```

Update playback progress.

**Request:**
```json
{
  "book_id": "book_12345",
  "chapter_id": 5,
  "position_seconds": 1200.0
}
```

## WebSocket (Future)

Real-time progress updates may be added via WebSocket for live playback tracking.

