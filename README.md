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

## Server (basement)

The unattended pipeline runs on a Linux host with an NVIDIA GPU, driven by a systemd user timer. The Mac sections below are legacy.

### Prerequisites

```bash
sudo apt install espeak-ng ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

```bash
make setup-cuda   # creates venv-cu128 (Python 3.12 via uv, CUDA 12.8 torch, MCP deps)
make check-cuda   # smoke-imports torch/TTS on CUDA, inside gpu-jobs.slice
```

`scripts/venv.sh` picks the venv for the server, tests and MCP server: `$AUDIOBOOK_VENV`, else `venv-cu128`, else `venv311`.

### Autopull env file

The unit reads `~/.config/audiobook/autopull.env` (systemd `EnvironmentFile`: `KEY=value`, no quotes, no spaces around `=`). Create it from the example and fill in the values yourself; never commit it:

```bash
mkdir -p ~/.config/audiobook
cp deploy/systemd/autopull.env.example ~/.config/audiobook/autopull.env
chmod 600 ~/.config/audiobook/autopull.env
```

Keys:

- `AUTOPULL_PUBLISH` - `0` is shadow mode (render and build the feed locally, upload nothing); `1` publishes.
- `AUDIOBOOK_MAX_CONCURRENT_CHUNKS` - parallel chunk renders.
- `AUDIOBOOK_HOST` - backend bind address.
- `AUDIOBOOK_NTFY_URL` - ntfy topic URL for phone notifications.
- `CLAUDE_CODE_OAUTH_TOKEN` - from `claude setup-token`, for headless commentary detection.
- `CLAUDE_CONFIG_DIR` - a claude config dir of its own, so headless `claude -p` loads none of your user hooks, plugins or CLAUDE.md.

Other settings (R2, Patreon cookie, voice sample) stay in the project `.env`; see Configuration.

### Enable the timer

Stop any manually started backend first (`make kill-dev`), so the timer's run does not collide with it. Then:

```bash
make install-timer
```

`make install-timer` refuses while the env file is missing, because autopull publishes by default. It links the units from `deploy/systemd` and enables `audiobook-autopull.timer` (every 15 minutes, at minutes 01, 16, 31 and 46).

Start in shadow mode (`AUTOPULL_PUBLISH=0`). Once a few runs look right, set `AUTOPULL_PUBLISH=1` in the env file; the next run picks it up. Remove the timer with `make uninstall-timer`.

### Logs

- `logs/autopull.log` - the run's own log.
- `journalctl --user -u audiobook-autopull` - the unit's output, including kills the script never sees.
- `systemctl --user list-timers audiobook-autopull.timer` - next and last run.

A failed run pushes an ntfy notification when `AUDIOBOOK_NTFY_URL` is set.

### Streaming (gpu-jobs.slice)

The service runs in `gpu-jobs.slice`, which freezes during a Sunshine stream, so rendering pauses and resumes on its own. `make check-cuda` runs in the same slice.

### Rollback to the Mac

Run `make uninstall-timer` on the server, turn publishing off if needed, then load `scripts/com.audiobook.autopull.plist` on the Mac again (copy it to `~/Library/LaunchAgents/` and `launchctl load` it). Never run both schedulers with publishing on.

## Mac setup (legacy)

### Prerequisites

- **Python 3.11** (required for TTS library compatibility)
- **Python 3.14+** (for general development)
- **Node.js** (for frontend)

On macOS with Homebrew:
```bash
brew install python@3.11 node
```

### Quick Start

#### 1. Check System Requirements

```bash
make check-system
```

#### 2. Setup

This creates two virtual environments:
- `venv` (Python 3.14+) - General dependencies
- `venv311` (Python 3.11) - TTS dependencies (required for audio generation)

```bash
make setup
```

#### 3. Run the Server

The server uses `venv311` which includes TTS support:

```bash
make dev
```

#### 4. Run the Frontend

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
./venv311/bin/pip install -r mcp_server/requirements.txt   # Mac, once: make setup already does this
```

It is registered in `.mcp.json`, so Claude Code launches it automatically through `scripts/venv.sh`
(`venv-cu128`, else `venv311`). The backend must be running (`make dev`). Config via env:
`AUDIOBOOK_API` (default `http://localhost:8000`), `AUDIOBOOK_FICTION_ID` (default `124774`).

## Dependencies

The Mac (legacy) setup uses two Python virtual environments; the server uses `venv-cu128` (see Server above):

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
