# Frontend Migration Guide

## Overview

The backend has been refactored to use `attr.s` models and `chapter_number` instead of `chapter_title` for API endpoints. This document outlines all the changes needed in the frontend to work with the new backend structure.

## Critical Changes Required

### 1. API Endpoint Changes: `chapter_title` → `chapter_number`

**All endpoints that used `chapter_title` now use `chapter_number` (integer).**

#### Changed Endpoints:

1. **Get Chunk Metadata**
   - **Old:** `/api/books/{book_id}/chapters/{chapter_title}/chunks`
   - **New:** `/api/books/{book_id}/chapters/{chapter_number}/chunks`
   - **Change:** Use `chapter_number` (integer) instead of `chapter_title` (string)

2. **Chunk Chapter**
   - **Old:** `POST /api/chapters/chunk` with `{ chapter_title: string }`
   - **New:** `POST /api/chapters/chunk` with `{ chapter_number: number }`
   - **Change:** Request body uses `chapter_number` instead of `chapter_title`

3. **Generate Chunks**
   - **Old:** `POST /api/chunks/generate` with `{ chapter_title: string }`
   - **New:** `POST /api/chunks/generate` with `{ chapter_number: number }`
   - **Change:** Request body uses `chapter_number` instead of `chapter_title`

4. **Generate Single Chunk**
   - **Old:** `POST /api/chunks/{chunk_index}/generate?chapter_title=...`
   - **New:** `POST /api/chunks/{chunk_index}/generate?chapter_number=...`
   - **Change:** Query parameter uses `chapter_number` instead of `chapter_title`

### 2. Response Structure Changes

#### Operation Results

All POST endpoints that return operation results now wrap the result in an `OperationResult` object:

```typescript
// Old structure (direct result)
{
  chunk_count: 5
}

// New structure (wrapped)
{
  status: "success",
  result: {
    book_id: "...",
    chapter_number: 1,
    chunk_count: 5,
    total_text_length: 12345
  }
}
```

**Affected endpoints:**
- `POST /api/chapters/chunk`
- `POST /api/chunks/generate`
- `POST /api/chunks/{chunk_index}/generate`
- `POST /api/books/download`
- `POST /api/chapters/download`

#### Book Stats Structure

The `BookStats` structure has changed significantly:

```typescript
// Old structure
{
  scraping: {
    total_chapters: 10,
    scraped_chapters: 8,
    last_scraped: "..."
  },
  tts: {
    total_chapters: 10,
    generated_chapters: 5,
    last_generated: "..."
  },
  chunks: {
    total_chunks: 50,
    chunks_by_chapter: { ... }
  }
}

// New structure (flat)
{
  book_id: "...",
  title: "...",
  total_chapters: 10,
  chapters_with_text: 8,
  chapters_with_audio: 5,
  chapters_chunked: 8,
  total_chunks: 50,
  completed_chunks: 45,
  pending_chunks: 5
}
```

#### Chapter Response Structure

The chapter detail endpoint (`GET /api/books/{book_id}/chapters/{chapter_number}`) now returns a `ChapterInfo` object:

```typescript
// New structure
{
  id: string | null,
  book_id: string,
  chapter_number: number,
  title: string,
  number: number | null,  // Royal Road number
  url: string | null,
  text_path: string | null,
  audio_urls: string[],  // Changed from audio_paths
  has_text: boolean,
  word_count: number | null,
  is_chunked: boolean,
  chunk_count: number,
  has_audio: boolean,
  stats: ChapterStats  // Nested stats object
}
```

**Key changes:**
- `audio_paths` → `audio_urls`
- Added `stats` nested object
- `id` is now `string | null` instead of `number | undefined`

#### Chunk Metadata Response

The chunk metadata endpoint response structure:

```typescript
// Response structure
{
  chapter_number: number,
  chapter_title: string,
  text_file: string | null,
  text_length: number,
  chunks: ChunkInfo[],
  flagged_chunks: number[]
}
```

**ChunkInfo structure:**
```typescript
{
  index: number,
  filename: string | null,
  path: string | null,
  url: string | null,
  flagged: boolean,
  text_start: number,
  text_end: number,
  text_length: number,
  status: string,  // "pending" | "running" | "completed" | "failed"
  generation_time_seconds: number | null
}
```

### 3. Type Definition Updates

#### Update `frontend/src/types/index.ts`:

```typescript
// BookStats - completely new structure
export interface BookStats {
  book_id: string
  title: string
  total_chapters: number
  chapters_with_text: number
  chapters_with_audio: number
  chapters_chunked: number
  total_chunks: number
  completed_chunks: number
  pending_chunks: number
}

// Chapter - update fields
export interface Chapter {
  id?: string  // Changed from number
  chapter_number: number
  title: string
  number?: number | null  // Royal Road number
  url?: string | null
  text_path?: string | null
  audio_urls?: string[]  // Changed from audio_paths
  is_chunked: boolean
  chunk_count: number
  has_audio: boolean
  scraped: boolean  // Maps to has_text
  word_count?: number | null
  duration_seconds?: number | null
  book_id?: string
  startTime?: number
  stats?: ChapterStats  // New nested stats
}

// ChapterStats - new interface
export interface ChapterStats {
  book_id: string
  chapter_number: number
  title: string
  has_text: boolean
  word_count: number | null
  text_size: number | null
  is_chunked: boolean
  chunk_count: number
  has_audio: boolean
  total_chunks: number
  completed_chunks: number
  pending_chunks: number
  failed_chunks: number
  flagged_chunks: number
}

// ChunksData - update field name
export interface ChunksData {
  chunks: ChunkMetadata[]
  chapter_number: number  // Changed from chapter_title
  text_length: number
}

// Job - update field name
export interface Job {
  id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  book_id?: string
  chapter_number?: number  // Changed from chapter_title
  message?: string
  created_at?: string
  updated_at?: string
}
```

### 4. Store Updates (`frontend/src/store/useAudiobookStore.ts`)

#### Update `loadChunkMetadata`:

```typescript
// Old
loadChunkMetadata: async (chapterTitle: string) => {
  const response = await fetch(
    `/api/books/${currentBook.id}/chapters/${encodeURIComponent(chapterTitle)}/chunks`
  )
}

// New
loadChunkMetadata: async (chapterNumber: number) => {
  const response = await fetch(
    `/api/books/${currentBook.id}/chapters/${chapterNumber}/chunks`
  )
}
```

#### Update `chunkChapter`:

```typescript
// Old
chunkChapter: async (chapterTitle: string, chunkDurationMinutes = 1.0) => {
  body: JSON.stringify({
    chapter_title: chapterTitle,
  })
  // Response: { result: ChunkChapterResult }
}

// New
chunkChapter: async (chapterNumber: number, chunkDurationMinutes = 1.0) => {
  body: JSON.stringify({
    chapter_number: chapterNumber,
  })
  // Response: { status: "success", result: ChunkChapterResult }
  const data = await response.json()
  return data.result  // Extract from OperationResult wrapper
}
```

#### Update `generateChunks`:

```typescript
// Old
generateChunks: async (chapterTitle: string, chunkIndices: number[] | null = null) => {
  body: JSON.stringify({
    chapter_title: chapterTitle,
  })
}

// New
generateChunks: async (chapterNumber: number, chunkIndices: number[] | null = null) => {
  body: JSON.stringify({
    chapter_number: chapterNumber,
  })
  // Response: { status: "success", result: GenerateChunksResult }
  const data = await response.json()
  return data.result
}
```

#### Update `generateSingleChunk`:

```typescript
// Old
generateSingleChunk: async (chapterTitle: string, chunkIndex: number) => {
  const response = await fetch(
    `/api/chunks/${chunkIndex}/generate?chapter_title=${encodeURIComponent(chapterTitle)}`
  )
}

// New
generateSingleChunk: async (chapterNumber: number, chunkIndex: number) => {
  const response = await fetch(
    `/api/chunks/${chunkIndex}/generate?chapter_number=${chapterNumber}`
  )
  // Response: { status: "success", result: GenerateChunksResult }
  const data = await response.json()
  return data.result
}
```

#### Update `setCurrentChapter`:

```typescript
// Old
if (chapter.is_chunked && chapter.chunk_count > 0) {
  await get().loadChunkMetadata(chapter.title)
}

// New
if (chapter.is_chunked && chapter.chunk_count > 0) {
  await get().loadChunkMetadata(chapter.chapter_number)
}
```

### 5. Component Updates

#### `ChapterActions.tsx`:

```typescript
// Old
const result = await chunkChapter(chapter.title, 1.0)
const result = await generateChunks(chapter.title, null)

// New
const result = await chunkChapter(chapter.chapter_number, 1.0)
const result = await generateChunks(chapter.chapter_number, null)
```

#### `AudioPlayer.tsx`:

```typescript
// Old
await loadChunkMetadata(chapterData.title)

// New
await loadChunkMetadata(chapterData.chapter_number)
```

#### `LibraryView.tsx`:

Update to use new `BookStats` structure:

```typescript
// Old
const scraping = stats?.scraping
const tts = stats?.tts
const chunks = stats?.chunks

// New
// Use flat stats structure
{book.stats?.total_chapters}
{book.stats?.chapters_with_text}
{book.stats?.chapters_with_audio}
{book.stats?.total_chunks}
```

### 6. Response Parsing Updates

All POST endpoints that return operation results need to extract the `result` field:

```typescript
// Pattern for all POST endpoints
const response = await fetch(...)
const data = await response.json()
if (data.status === "success") {
  return data.result  // Extract actual result
} else {
  throw new Error(data.error || "Operation failed")
}
```

## Migration Checklist

- [ ] Update all API calls to use `chapter_number` instead of `chapter_title`
- [ ] Update `loadChunkMetadata` to accept `chapter_number` instead of `chapter_title`
- [ ] Update `chunkChapter` to use `chapter_number` and extract result from `OperationResult`
- [ ] Update `generateChunks` to use `chapter_number` and extract result from `OperationResult`
- [ ] Update `generateSingleChunk` to use `chapter_number` and extract result from `OperationResult`
- [ ] Update TypeScript types for `BookStats`, `Chapter`, `ChapterStats`
- [ ] Update `LibraryView` to use new flat `BookStats` structure
- [ ] Update all components that call store methods with `chapter.title` to use `chapter.chapter_number`
- [ ] Update response parsing to handle `OperationResult` wrapper
- [ ] Update `Chapter` interface: `audio_paths` → `audio_urls`, `id` type change
- [ ] Test all API endpoints work correctly
- [ ] Test chunking workflow
- [ ] Test audio generation workflow
- [ ] Test chapter navigation

## Testing Checklist

- [ ] Load books list - verify stats display correctly
- [ ] Select a book - verify chapters load
- [ ] Select a chapter - verify audio URLs load
- [ ] Chunk a chapter - verify chunking works
- [ ] Generate chunks - verify generation works
- [ ] Play audio - verify chunked audio plays correctly
- [ ] Navigate between chapters - verify state persists
- [ ] Refresh book - verify data updates correctly

