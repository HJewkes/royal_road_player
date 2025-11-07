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
python scripts/find_book.py "Player Manager Ted Steele"
```

#### 2. Download Chapters

```bash
# Download all chapters from a book (easiest method)
python scripts/scrape_book.py "https://www.royalroad.com/fiction/12345/book-title"

# Download specific book number from a series
python scripts/scrape_book.py "URL" -b 7

# Test with limited chapters
python scripts/scrape_book.py "URL" -m 5

# Custom output directory
python scripts/scrape_book.py "URL" -o ./my_books

# Alternative: Using module (requires PYTHONPATH)
PYTHONPATH=. python -m src.scraper.royal_road "URL" -b 7
```

#### 3. Generate Annotations (Phase 3 - Coming Soon)

```bash
python -m src.llm.annotator --book-id "book_12345"
```

#### 4. Convert to Audio (Phase 2 - Coming Soon)

```bash
python -m src.tts.generator --book-id "book_12345"
```

#### 5. Start Web App (Phase 4 - Coming Soon)

```bash
make run
```

## Documentation

- [Setup Guide](SETUP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Project Plan](.archive/plans/PHASE_0_PROJECT_PLAN.md)

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

