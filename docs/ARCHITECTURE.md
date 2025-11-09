# Architecture

> **Status:** Current  
> **Last Updated:** 2025-11-09

## System Overview

The audiobook system consists of four main components:

1. **Web Scraper** - Downloads chapters from Royal Road ✅
2. **TTS Engine** - Converts text to high-quality audio using XTTS v2 ✅
3. **Web Application** - Provides playback interface with job management ✅
4. **LLM Annotator** - Adds prosody annotations using local LLM (Future)

## Component Architecture

### Web Scraper (`backend/src/scraper/`)

- **royal_road_client.py**: Royal Road API client
- **royal_road_controller.py**: Scraping controller
- **html_processor.py**: HTML extraction and cleaning
- **formatter.py**: Text formatting utilities

**Flow:**
1. Parse book page to get chapter list
2. For each chapter, fetch and parse HTML
3. Extract main content, filter navigation/ads
4. Convert to clean text using `process_html_for_storage`
5. Save text file with metadata via `ChapterController`

### TTS System (`backend/src/tts/`)

- **engine.py**: XTTS v2 TTS engine implementation
- **voice_registry.py**: Voice sample management and registry

**Flow:**
1. Load XTTS v2 model (cached after first load)
2. Resolve voice from registry (by name)
3. Generate audio chunks with voice cloning
4. Save chunked audio files with metadata

### Text Processing (`backend/src/text_processing/`)

- **normalizer.py**: Text normalization (numbers, dates, acronyms)
- **segmenter.py**: Breath-group segmentation
- **chunker.py**: Text chunking (respects XTTS v2 250-char limit)
- **chunk_metadata.py**: Chunk-level synthesis metadata (voice, speed, pauses)
- **processor.py**: Unified text processing pipeline
- **config.py**: Text processing configuration

**Flow:**
1. Extract HTML to text
2. Normalize text (numbers, dates, punctuation)
3. Chunk text at paragraph breaks (max 250 chars per chunk)
4. Attach synthesis metadata (voice_name, speed, pauses)

### Controllers (`backend/src/controllers/`)

Controllers provide single-responsibility business logic operations:

- **BookController**: Book-level operations (list, get, stats)
- **ChapterController**: Chapter-level operations (get, chunks, stats)
- **ChunkController**: Chunk-level operations (get, update status)
- **ChunkingController**: Multi-chunk operations (chunk a chapter)
- **TTSController**: Audio generation operations

**Architecture Principles:**
- **Models**: Data + computed accessors (e.g., `has_audio`, `chunk_count`)
- **Controllers**: Operations + business logic
- **DataSynchronizer**: Persistence layer (filesystem ↔ models)

### Data Layer (`backend/src/data/`)

- **data_synchronizer.py**: Persistence layer for models
  - Loads models from filesystem
  - Saves models to filesystem
  - Keeps models and filesystem in sync

### LLM Annotator (`backend/src/llm/`)

- **ollama_client.py**: Ollama API client
- **annotation_prompt.py**: Prompt engineering

**Flow:**
1. Load text chapter
2. Generate annotation prompt
3. Call Ollama API
4. Parse JSON response
5. Validate annotations
6. Save annotation file

### Web Application (`backend/src/web/`)

- **app.py**: FastAPI application with static file serving
- **routes.py**: REST API endpoints (books, chapters, chunks)
- **models/**: Request/response models

**Frontend (`frontend/`):**
- **TypeScript/React SPA**: Modern React application with TypeScript
- **Components**: Modular React components with CSS modules
- **State Management**: Zustand for global state
- **Build System**: Vite for fast development and optimized production builds
- **Type Safety**: Full TypeScript coverage with strict type checking

**Flow:**
1. User navigates to library view
2. API lists all books with metadata
3. User selects book → loads chapters
4. User selects chapter → loads chunked audio
5. HTML5 Audio API plays chunks sequentially
6. Progress tracked in URL params + localStorage

### Job Queue & Real-Time Updates (`backend/src/services/`)

The system uses a background job queue with Server-Sent Events (SSE) for real-time status updates.

**Components:**

- **job_queue.py**: Background processor that polls database for pending chunks and generates audio
- **queue_events.py**: Event manager that broadcasts status updates via SSE
- **SSE Endpoint** (`/api/queue/events`): Streams real-time events to connected clients

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│ Background Processor (Async Task)                           │
│                                                             │
│  while True:                                               │
│    ┌─────────────────────────────────────┐                 │
│    │ Poll Database (every 1 second)     │                 │
│    │ ChunkRepository.get_pending_...()   │                 │
│    └──────────────┬──────────────────────┘                 │
│                   │                                          │
│                   ▼                                          │
│    ┌─────────────────────────────────────┐                 │
│    │ process_next()                      │                 │
│    │ 1. Query DB → Get pending chunk    │                 │
│    │ 2. Update DB → Mark as RUNNING      │                 │
│    │ 3. ⚡ IMMEDIATE: broadcast_started()│                 │
│    │ 4. Generate audio (slow, 5-30s)    │                 │
│    │ 5. Update DB → Mark COMPLETED       │                 │
│    │ 6. ⚡ IMMEDIATE: broadcast_completed()│                │
│    └──────────────┬──────────────────────┘                 │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ await event_manager.broadcast_*()
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Event Manager (In-Memory)                                   │
│                                                             │
│  _connections = {                                           │
│    Queue1 (Client 1),                                      │
│    Queue2 (Client 2),                                      │
│    ...                                                      │
│  }                                                          │
│                                                             │
│  broadcast(event, data):                                   │
│    for queue in _connections:                              │
│      queue.put_nowait(message)  ⚡ INSTANT                 │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    │ Messages pushed to queues
                    │
        ┌───────────┴───────────┐
        │                      │
        ▼                      ▼
┌──────────────┐      ┌──────────────┐
│ SSE Client 1 │      │ SSE Client 2 │
│              │      │              │
│ queue.get()  │      │ queue.get()  │
│ (blocks)     │      │ (blocks)     │
│              │      │              │
│ yield event  │      │ yield event  │
└──────────────┘      └──────────────┘
```

**Key Points:**

1. **Database Polling (Only for Finding Work)**
   - Background processor polls database every 1 second
   - Queries: `SELECT * FROM chunks WHERE status='pending' ORDER BY ...`
   - Purpose: Find new work to process

2. **Event Pushing (Immediate, No Polling)**
   - When job completes → `await event_manager.broadcast_*()` called
   - Pushes message to **in-memory `asyncio.Queue`** for each SSE client
   - No database involved - pure in-memory push
   - No polling - SSE endpoint blocks on `queue.get()` until event arrives

3. **SSE Endpoint (Blocking Read, Not Polling)**
   - Each SSE client has its own `asyncio.Queue`
   - Endpoint does `await queue.get()` - **blocks** until event arrives
   - When event arrives → immediately yields to client
   - No polling - event-driven blocking read

**Event Types:**
- `job_started`: Job begins processing
- `job_completed`: Job finished successfully
- `job_failed`: Job failed with error
- `status`: Full queue status update (includes ETA)

**Frontend Integration:**

- **React Hook** (`frontend/src/hooks/useQueueEvents.ts`): Manages SSE connection lifecycle
- **Automatic Reconnection**: Exponential backoff (1s → 2s → 4s → 8s → max 30s)
- **Components**: `QueueStatusFlyout` uses SSE (others can migrate similarly)

**Benefits:**

✅ **Real-time updates** - Status changes pushed immediately when jobs start/complete/fail  
✅ **Reduced server load** - No constant polling requests (was 5-15s intervals)  
✅ **Better UX** - Instant feedback when jobs complete  
✅ **Automatic reconnection** - Handles network issues gracefully  
✅ **Efficient** - In-memory queues, no database overhead for events  

**Performance:**

- **Before (Polling)**: 5-15 second intervals, ~240-720 requests/hour per component
- **After (SSE)**: Single persistent connection, updates only when status changes, ~0 requests/hour (just keepalive)

## Data Flow

```
Royal Road → Scraper → Text Files → DataSynchronizer
                              ↓
                         Text Processing → Chunks with Metadata
                              ↓
                         TTS Engine (XTTS v2) → Chunked Audio Files
                              ↓
                         DataSynchronizer (chunk positions, status)
                              ↓
                         Web App → Chunked Playback with Timeline
```

**Key Features:**
- **Chunked Audio**: Large chapters split into ~1-minute chunks (max 250 chars per chunk)
- **Metadata Tracking**: Text positions, chunk status, generation times
- **Voice Registry**: Centralized voice management by name
- **Chunk Metadata**: Per-chunk synthesis parameters (voice_name, speed, pauses)

## Project Structure

The project is organized with clear separation between Python backend and TypeScript frontend:

- **`backend/`**: Python backend code (scraper, TTS, controllers, web API)
  - **`backend/src/`**: Source code
  - **`backend/tests/`**: Test code (mirrors src/)
  - **`backend/requirements.txt`**: Python dependencies
- **`frontend/`**: TypeScript/React frontend code (components, state, styles, types)
- **`frontend/dist/`**: Built frontend assets (generated from `frontend/`)
- **`data/`**: Runtime data (books, audio files, databases)
- **`scripts/`**: Utility scripts for common tasks

## Technology Stack

- **Backend**: Python 3.11, FastAPI
- **Scraping**: BeautifulSoup4, Requests
- **TTS**: Coqui TTS XTTS v2 (voice cloning, 250-char limit, English only)
- **Data Storage**: JSON metadata files + filesystem
- **Frontend**: TypeScript, React 18, Vite, Zustand, Lucide React icons

## Future Enhancements

- Support for other book sources
- Multiple TTS voices per book (via voice registry)
- Cloud sync for progress
- Mobile app
- Streaming audio generation
