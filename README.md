# Audiobook System

A comprehensive local audiobook system for Royal Road books with high-quality text-to-speech and web-based playback controls.

## Features

- **Web Scraping:** Download chapters from Royal Road automatically
- **Text Formatting:** Clean, well-formatted text files
- **LLM Annotation:** Automatic text annotation for inflection and timing using local LLM
- **High-Quality TTS:** Local text-to-speech conversion with annotation support
- **Web Playback:** Local web app with full playback controls

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend development)
- 8GB+ RAM (16GB recommended for TTS)
- 10GB+ free storage

### Installation

```bash
# One-command setup (installs Ollama, TTS, and all dependencies)
make setup

# Optional: Pull default LLM model for annotations
make setup-ollama-model
```

### Usage

#### 1. Find a Book on Royal Road

```bash
# Using Python module CLI (from project root)
cd backend && python -m src.scraper.royal_road --help

# Search for books (via Python API)
cd backend && python -c "from src.scraper.royal_road import RoyalRoadScraper; scraper = RoyalRoadScraper(); print(scraper.search_royal_road('Player Manager Ted Steele'))"
```

#### 2. Download Chapters

```bash
# Download all chapters from a book (from project root)
cd backend && python -m src.scraper.royal_road "https://www.royalroad.com/fiction/12345/book-title"

# Download specific book number from a series
cd backend && python -m src.scraper.royal_road "URL" -b 7

# Test with limited chapters
cd backend && python -m src.scraper.royal_road "URL" -m 5

# Custom output directory
cd backend && python -m src.scraper.royal_road "URL" -o ./my_books
```

#### 3. Generate Audio

Audio generation is handled through the web interface. You can also use the Python API directly:

```python
# From backend directory or with PYTHONPATH=backend
from src.tts.generator import AudioGenerator
from pathlib import Path

generator = AudioGenerator()
audio_files = generator.generate_chapter_chunked(
    text_path=Path("data/books/.../chapters/07-01 - Chapter Title.txt"),
    chunk_duration_minutes=1.0
)
```

#### 4. Start Web App

```bash
make run
# Then open http://localhost:8000 in your browser
```

The web app provides:
- Library view with all downloaded books
- Chapter playback with progress tracking
- Background job management (scraping, audio generation)
- Series discovery and book search
- Chunk timeline visualization

## Documentation

The `docs/` directory focuses on setup and architecture:

- **[SETUP.md](SETUP.md)** - Complete setup guide
- **[docs/TTS_SETUP.md](docs/TTS_SETUP.md)** - Text-to-speech setup instructions and model configuration
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, component overview, project structure, and data flow

### Additional Documentation

Additional guides and reference documentation are archived in [`.archive/docs/`](.archive/docs/):

**Reference:**
- **API.md** - REST API reference with all endpoints and request/response formats
- **TTS_OPTIMIZATION_GUIDE.md** - Performance optimization guide for TTS processing
- **XTTS_V2_TEXT_PREPARATION.md** - Text preparation guide for XTTS v2 model
- **DATA_SYNCHRONIZER_USAGE.md** - Guide for using the data synchronizer

**Analysis & Audits:**
- **CODEBASE_AUDIT.md** - Codebase audit findings
- **CODE_REVIEW_HIGH_VALUE_IMPROVEMENTS.md** - Code review improvements
- **TTS_PERFORMANCE_AUDIT.md** - TTS performance analysis
- **PLAYER_AESTHETIC_IMPROVEMENTS_SUMMARY.md** - Player UI improvements summary
- **PLAYER_DESIGN_IMPROVEMENTS.md** - Player design improvements
- **CHATTERBOX_ANALYSIS.md** - Analysis of external project features
- **TTS_QUICK_OPTIMIZATION.md** - Quick optimization guide (consolidated into TTS_OPTIMIZATION_GUIDE.md)

## Development

### Running Tests
```bash
make test
```

### Code Quality
```bash
make lint
make format
```

## License

MIT

