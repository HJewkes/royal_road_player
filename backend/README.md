# Backend

Python backend for the Audiobook system.

## Structure

```
backend/
├── src/                    # Python source code
│   ├── scraper/           # Web scraping modules
│   ├── tts/               # Text-to-speech engine
│   ├── llm/               # LLM annotation modules
│   ├── services/          # Business logic services
│   ├── utils/             # Utility functions
│   └── web/               # FastAPI backend
├── tests/                 # Test code (mirrors src/)
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
└── pytest.ini            # Test configuration
```

## Development

### Prerequisites

- Python 3.10+ (Python 3.11 recommended for TTS support)
- Virtual environment (created at project root)

### Setup

From the project root:

```bash
# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
```

### Running

From the project root:

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
cd backend && python -m src.web.app --reload

# Or use Makefile
make dev
```

### Testing

From the project root:

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
cd backend && pytest tests/ -v

# Run with coverage
cd backend && pytest tests/ --cov=src --cov-report=html

# Or use Makefile
make test
make test-coverage
```

### Linting & Formatting

From the project root:

```bash
# Activate virtual environment
source venv/bin/activate

# Format code
cd backend && black src tests
cd backend && isort src tests

# Lint code
cd backend && flake8 src tests
cd backend && pylint src
cd backend && mypy src

# Or use Makefile
make format
make lint
```

## Module CLI

The scraper can be run as a module:

```bash
# From project root
cd backend && python -m src.scraper.royal_road "https://www.royalroad.com/fiction/12345/book-title"
```

## Python API

Import and use the backend modules directly:

```python
from src.scraper.royal_road import RoyalRoadScraper
from src.tts.generator import AudioGenerator
from src.services.book_service import BookService

# Search for books
scraper = RoyalRoadScraper()
results = scraper.search_royal_road("Player Manager")

# Generate audio
generator = AudioGenerator()
audio_files = generator.generate_chapter_chunked(
    text_path=Path("chapter.txt"),
    chunk_duration_minutes=1.0
)
```

