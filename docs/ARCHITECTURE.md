# Architecture

> **Status:** Draft  
> **Last Updated:** 2025-01-27

## System Overview

The audiobook system consists of four main components:

1. **Web Scraper** - Downloads chapters from Royal Road
2. **TTS Engine** - Converts text to high-quality audio
3. **LLM Annotator** - Adds prosody annotations using local LLM
4. **Web Application** - Provides playback interface

## Component Architecture

### Web Scraper (`src/scraper/`)

- **royal_road.py**: Main scraper for Royal Road chapters
- **formatter.py**: HTML to text conversion and cleaning

**Flow:**
1. Parse book page to get chapter list
2. For each chapter, fetch and parse HTML
3. Extract main content, filter navigation/ads
4. Convert to clean text
5. Save text file with metadata

### TTS System (`src/tts/`)

- **engine.py**: TTS engine abstraction (Coqui/Piper)
- **annotator.py**: Annotation parser and processor
- **generator.py**: Audio generation pipeline

**Flow:**
1. Load TTS model
2. Parse annotations (if provided)
3. Apply annotations to text/prosody
4. Generate audio file
5. Save audio with metadata

### LLM Annotator (`src/llm/`)

- **ollama_client.py**: Ollama API client
- **annotation_prompt.py**: Prompt engineering

**Flow:**
1. Load text chapter
2. Generate annotation prompt
3. Call Ollama API
4. Parse JSON response
5. Validate annotations
6. Save annotation file

### Web Application (`src/web/`)

- **app.py**: FastAPI application
- **models.py**: Database models
- **routes.py**: API endpoints

**Flow:**
1. User requests book/chapter
2. API retrieves metadata
3. Frontend loads audio file
4. HTML5 Audio API plays audio
5. Progress tracked in database

## Data Flow

```
Royal Road → Scraper → Text Files
                              ↓
                         LLM Annotator → Annotation JSON
                              ↓
                         TTS Engine → Audio Files
                              ↓
                         Web App → Playback
```

## Technology Stack

- **Backend**: Python 3.10+, FastAPI
- **Scraping**: BeautifulSoup4, Requests
- **TTS**: Coqui TTS or Piper TTS
- **LLM**: Ollama (local)
- **Database**: SQLite (via SQLAlchemy)
- **Frontend**: HTML5, CSS, JavaScript

## Directory Structure

See [Project Plan](.archive/plans/PHASE_0_PROJECT_PLAN.md) for detailed structure.

## Future Enhancements

- Support for other book sources
- Multiple TTS voices per book
- Cloud sync for progress
- Mobile app
- Streaming audio generation

