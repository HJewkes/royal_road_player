# Architecture

> **Status:** Current  
> **Last Updated:** 2025-01-27

## System Overview

The audiobook system consists of four main components:

1. **Web Scraper** - Downloads chapters from Royal Road ✅
2. **TTS Engine** - Converts text to high-quality audio using XTTS v2 ✅
3. **Web Application** - Provides playback interface with job management ✅
4. **LLM Annotator** - Adds prosody annotations using local LLM (Future)

## Component Architecture

### Web Scraper (`backend/src/scraper/`)

- **royal_road.py**: Main scraper for Royal Road chapters
- **formatter.py**: HTML to text conversion and cleaning

**Flow:**
1. Parse book page to get chapter list
2. For each chapter, fetch and parse HTML
3. Extract main content, filter navigation/ads
4. Convert to clean text
5. Save text file with metadata

### TTS System (`backend/src/tts/`)

- **generator.py**: Audio generation pipeline with chunking
- **chunker.py**: Text chunking (respects XTTS v2 250-char limit)
- **normalizer.py**: Text normalization (numbers, dates, acronyms)
- **segmenter.py**: Breath-group segmentation
- **voice_registry.py**: Voice sample management
- **dsl_mapper.py**: Micro-SSML DSL parsing (future)

**Flow:**
1. Load XTTS v2 model (cached after first load)
2. Normalize text (numbers, dates, punctuation)
3. Chunk text at paragraph breaks (max 250 chars per chunk)
4. Generate audio chunks with voice cloning
5. Save chunked audio files with metadata
6. Update metadata tracker with chunk positions and status

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
- **routes.py**: REST API endpoints (books, chapters, jobs, chunks)
- **jobs.py**: Background job management (scraping + audio generation queues)
- **book_discovery.py**: Royal Road series discovery and book search
- **database.py**: SQLite database for progress tracking

**Metadata Tracking (`backend/src/utils/metadata_tracker.py`):**
- Book/chapter/chunk metadata tracking

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
7. Background jobs polled for real-time updates

## Data Flow

```
Royal Road → Scraper → Text Files → Metadata Tracker
                              ↓
                         TTS Engine (XTTS v2) → Chunked Audio Files
                              ↓
                         Metadata Tracker (chunk positions, status)
                              ↓
                         Web App → Chunked Playback with Timeline
```

**Key Features:**
- **Chunked Audio**: Large chapters split into ~1-minute chunks
- **Metadata Tracking**: Text positions, chunk status, generation times
- **Background Jobs**: Separate queues for scraping (I/O) and audio (GPU)
- **Real-time Updates**: Polling for job status and chunk completion

## Project Structure

The project is organized with clear separation between Python backend and TypeScript frontend:

- **`backend/`**: Python backend code (scraper, TTS, services, web API)
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
- **TTS**: Coqui TTS XTTS v2 (voice cloning, 250-char limit)
- **Database**: SQLite (via SQLAlchemy) + JSON metadata files
- **Frontend**: TypeScript, React 18, Vite, Zustand, Lucide React icons
- **Job Management**: asyncio + subprocess with live output streaming

## Directory Structure

See [Project Plan](.archive/plans/PHASE_0_PROJECT_PLAN.md) for detailed structure.

## Future Enhancements

- Support for other book sources
- Multiple TTS voices per book
- Cloud sync for progress
- Mobile app
- Streaming audio generation

