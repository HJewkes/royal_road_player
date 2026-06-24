# Audiobook

A streamlined audiobook production system for converting Royal Road web fiction to audiobooks.

## Key Features

- **Filesystem-based state**: No database required - all state is derived from file existence
- **Chapter-by-chapter processing**: Completes one chapter before moving to the next
- **Auto-export on completion**: Chapters are automatically exported when all chunks complete
- **STT Validation**: Validate generated audio against source text using Whisper
- **Simple workflow**: Scrape → Normalize → Chunk → Generate → Validate → Export

## Directory Structure

```
audiobook/
├── backend/
│   ├── src/
│   │   ├── api/           # FastAPI routes
│   │   ├── scraper/       # Royal Road scraper
│   │   ├── text/          # Normalization + chunking
│   │   ├── tts/           # XTTS v2 engine
│   │   ├── validation/    # STT validation
│   │   ├── export/        # Audio concatenation
│   │   ├── queue/         # Job processing
│   │   ├── discovery.py   # Filesystem discovery
│   │   ├── models.py      # Pydantic models
│   │   └── config.py      # Settings
│   ├── tests/
│   └── main.py
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── Dashboard.tsx
│       └── BookView.tsx
├── data/
│   ├── books/             # Book data
│   │   └── {fiction_id}/
│   │       └── book_{N}/
│   │           ├── metadata.json
│   │           └── chapters/
│   │               └── chapter_{N}/
│   │                   ├── raw.txt
│   │                   ├── normalized.txt
│   │                   ├── chunks/
│   │                   │   ├── 001.txt
│   │                   │   └── 001.wav
│   │                   ├── validation.json
│   │                   └── audio.wav
│   └── cache/
│       └── stt/           # Whisper cache
└── exports/               # Final audio files
```

## Prerequisites

- **Python 3.11** (required for TTS library compatibility)
- **Python 3.14+** (for general development)
- **Node.js** (for frontend)

On macOS with Homebrew:
```bash
brew install python@3.11 node
```

## Quick Start

### 1. Check System Requirements

```bash
make check-system
```

### 2. Setup

This creates two virtual environments:
- `venv` (Python 3.14+) - General dependencies
- `venv311` (Python 3.11) - TTS dependencies (required for audio generation)

```bash
make setup
```

### 3. Run the Server

The server uses `venv311` which includes TTS support:

```bash
make dev
```

### 4. Run the Frontend

```bash
make frontend-setup  # First time only
make frontend-dev
```

Or run both together:

```bash
make dev-all
```

Open http://localhost:5173 to access the web UI.

## API Endpoints

### Discovery

- `GET /api/fictions` - List all fiction IDs
- `GET /api/books/{fiction_id}` - List books for a fiction
- `GET /api/books/{fiction_id}/{book_number}` - Get book details
- `GET /api/books/{fiction_id}/{book_number}/chapters` - List chapters

### Scraping

- `GET /api/scraper/preview?fiction_id=X&book_number=Y` - Preview chapters
- `POST /api/scraper/download` - Download a book

### Text Processing

- `POST /api/normalize` - Normalize chapter text
- `POST /api/chunk` - Chunk normalized text

### Audio Generation

- `POST /api/generate` - Queue chapters for audio generation
- `GET /api/queue/status` - Get queue status
- `GET /api/queue/chapter/{fiction_id}/{book_number}/{chapter_number}` - Chapter status
- `POST /api/queue/retry` - Retry failed jobs

### Validation

- `POST /api/validate` - Validate a chapter
- `GET /api/validation/{fiction_id}/{book_number}/{chapter_number}` - Get results

### Export

- `POST /api/export` - Export chapter to audio file
- `GET /api/export/status/{fiction_id}/{book_number}` - Get export status

### Events

- `GET /api/events?since=<id>&type=<type>&limit=<n>` - Poll pipeline events (append-only
  log at `logs/events.jsonl`; integer `id` is the cursor). Emitted: `chapter.completed`,
  `run.error`.
- `POST /api/events` - Emit an event (used by `autopull.sh` for `run.error`)

## MCP Server

`mcp_server/audiobook_mcp.py` is a thin FastMCP adapter over the API so a Claude agent can
observe and drive the pipeline (tools: `audiobook_status`, `audiobook_pending`,
`audiobook_events`, `audiobook_queue`, `audiobook_process`, `audiobook_retry`,
`audiobook_books`). It holds no logic of its own — every tool is an HTTP call to the
running backend.

```bash
./venv/bin/pip install -r mcp_server/requirements.txt   # one-time: mcp + httpx into venv
```

It is registered in `.mcp.json`, so Claude Code launches it automatically (`venv/bin/python
mcp_server/audiobook_mcp.py`). The backend must be running (`make dev`). Config via env:
`AUDIOBOOK_API` (default `http://localhost:8000`), `AUDIOBOOK_FICTION_ID` (default `124774`).

## Dependencies

The project uses two Python virtual environments:

- **venv** (Python 3.14+): General dependencies (`backend/requirements.txt`)
  - FastAPI, web scraping, text processing, etc.
  
- **venv311** (Python 3.11): TTS dependencies (`backend/requirements-tts.txt`)
  - Coqui TTS, PyTorch, Whisper for validation
  - **Required for audio generation**

The `make setup` command automatically creates both environments. The development server (`make dev`) uses `venv311` to ensure TTS functionality is available.

## Configuration

Environment variables (in `.env`):

```env
# TTS Settings
AUDIOBOOK_TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
AUDIOBOOK_VOICE_SAMPLE_PATH=/path/to/voice.wav

# Validation
AUDIOBOOK_WHISPER_MODEL=base
AUDIOBOOK_VALIDATION_THRESHOLD=0.90

# Server
AUDIOBOOK_HOST=0.0.0.0
AUDIOBOOK_PORT=8000
AUDIOBOOK_DEBUG=false
```

## State Derivation

Status is determined by file existence:

| Files Present | Status |
|--------------|--------|
| `raw.txt` | Downloaded |
| `normalized.txt` | Normalized |
| `chunks/*.txt` | Chunked |
| All `chunks/*.wav` | Audio Complete |
| `validation.json` | Validated |
| `audio.wav` | Chapter Ready |
| In `exports/` | Exported |

## Development

### Run Tests

```bash
make test
```

### Lint

```bash
make lint
```

### Format

```bash
make format
```

### Clean Rebuild

```bash
make rebuild
```

## License

Private project - not for distribution.
