# Audiobook System - Project Plan

> **Created:** 2025-01-27  
> **Status:** Planning Phase  
> **Project Goal:** Build a complete local audiobook system for Royal Road books with high-quality TTS and web-based playback

---

## Project Overview

A comprehensive local audiobook system that:
1. **Scrapes** chapters from Royal Road
2. **Formats** chapters into clean text files
3. **Annotates** text with TTS metadata (inflection, timing) using local LLM
4. **Converts** annotated text to high-quality audio using local TTS
5. **Provides** web-based playback interface with full controls

---

## Technology Stack Decisions

### Web Scraping
- **Library:** `beautifulsoup4` + `requests` (Python)
- **Rationale:** Mature, reliable, handles dynamic content well
- **Alternative:** `selenium` if JavaScript rendering needed

### TTS System
- **Primary:** Coqui TTS (XTTS v2) - High quality, multilingual, controllable
- **Alternative:** Piper TTS - Fast, lightweight, good quality
- **SSML Support:** Custom annotation layer (Coqui supports prosody control via API)
- **Rationale:** Coqui XTTS v2 offers best quality-to-speed ratio for local models

### LLM for Annotation
- **Primary:** Ollama (via API) - Easy local setup, supports multiple models
- **Models:** Llama 3.1 8B or Mistral 7B (for annotation tasks)
- **Rationale:** Need reasoning capability to understand context and add appropriate annotations

### Web Framework
- **Backend:** FastAPI (Python) - Modern, fast, auto-docs, WebSocket support
- **Frontend:** Vanilla HTML/CSS/JS - Simple, no build step, easy to customize
- **Audio Playback:** HTML5 Audio API + custom controls
- **Rationale:** FastAPI provides async support for long TTS operations, WebSocket for progress updates

---

## Phase Breakdown

### Phase 1: Royal Road Web Scraper
**Goal:** Download and format chapters from Royal Road

**Success Metrics:**
- ✅ Successfully download 100% of chapters from a test book (10+ chapters)
- ✅ Text extraction accuracy: >95% clean text (no HTML artifacts)
- ✅ Chapter ordering preserved correctly
- ✅ Handle rate limiting gracefully (respect robots.txt, delays)
- ✅ Error recovery: Resume from last successful chapter on failure
- ✅ Processing time: <2 seconds per chapter (excluding network)

**Deliverables:**
- Royal Road scraper module
- Text formatter (clean HTML → plain text)
- Chapter metadata extractor (title, number, author notes)
- Error handling and retry logic
- Golden dataset: 10 chapters from a test book

**Technical Approach:**
- Parse Royal Road chapter pages
- Extract main content, filter navigation/ads
- Handle author notes separately
- Save as structured text files (one per chapter)
- Store metadata (chapter number, title, word count)

---

### Phase 2: TTS System Integration
**Goal:** Convert text to high-quality audio with annotation support

**Success Metrics:**
- ✅ Audio quality: MOS score >4.0 (subjective, but natural-sounding)
- ✅ Annotation support: Successfully apply prosody changes (pitch, speed, pauses)
- ✅ Processing speed: >150 words/minute generation
- ✅ Audio format: WAV 22050Hz 16-bit (or MP3 128kbps)
- ✅ Error rate: <1% failed generations
- ✅ Memory usage: <8GB RAM for model loading

**Deliverables:**
- TTS engine wrapper (Coqui/Piper)
- Annotation parser (custom format → TTS parameters)
- Audio generation pipeline
- Batch processing support
- Progress tracking
- Golden dataset: 5 annotated chapters → audio

**Technical Approach:**
- Install and configure Coqui TTS or Piper
- Create annotation format (JSON or custom markup)
- Map annotations to TTS API calls
- Generate audio files (one per chapter)
- Store audio metadata (duration, file size, generation time)

**Annotation Format (Proposed):**
```json
{
  "text": "Hello world",
  "annotations": [
    {"type": "pause", "position": 5, "duration_ms": 500},
    {"type": "emphasis", "position": 0, "strength": 1.2},
    {"type": "pitch", "position": 6, "shift": 0.1}
  ]
}
```

---

### Phase 3: LLM-Based Text Annotation
**Goal:** Automatically annotate text with TTS metadata using local LLM

**Success Metrics:**
- ✅ Annotation accuracy: >80% of annotations improve perceived quality (subjective test)
- ✅ Text preservation: 100% original text unchanged (annotations are metadata)
- ✅ Processing speed: >500 words/minute annotation
- ✅ Context awareness: Correctly identifies dialogue, narration, emphasis
- ✅ False positive rate: <10% unnecessary annotations
- ✅ Consistency: Same text produces similar annotations across runs

**Deliverables:**
- LLM integration (Ollama client)
- Annotation prompt engineering
- Annotation parser (LLM output → annotation format)
- Validation system (check annotation format)
- Golden dataset: 10 chapters with human-validated annotations

**Technical Approach:**
- Use Ollama API to analyze text
- Prompt LLM to identify:
  - Dialogue vs narration
  - Emphasis points
  - Natural pause locations
  - Emotional tone shifts
- Output annotations as JSON metadata
- Store annotations separately from text (preserve original)

**Annotation Types:**
- Pauses (sentence breaks, paragraph breaks, dramatic pauses)
- Emphasis (important words, dialogue emphasis)
- Pitch shifts (questions, exclamations, character voices)
- Speed changes (fast-paced action, slow contemplation)

---

### Phase 4: Web Application with Playback Controls
**Goal:** Local web app for audiobook playback

**Success Metrics:**
- ✅ Playback controls: Play, pause, seek, speed (0.5x-2.0x), chapter navigation
- ✅ Progress tracking: Save/listen position per book
- ✅ UI responsiveness: <100ms response to user actions
- ✅ Audio quality: No stuttering, smooth playback
- ✅ Chapter loading: <2 seconds to load next chapter
- ✅ Browser compatibility: Works in Chrome, Firefox, Safari (latest versions)
- ✅ Mobile-friendly: Responsive design for mobile browsers

**Deliverables:**
- FastAPI backend server
- HTML/CSS/JS frontend
- Audio player component
- Chapter list/navigation
- Progress persistence (SQLite)
- Book management (list books, select book)
- API endpoints for all operations

**Technical Approach:**
- FastAPI serves static files + API endpoints
- REST API for book/chapter metadata
- WebSocket for real-time progress updates (optional)
- SQLite database for progress tracking
- HTML5 Audio API for playback
- Custom controls overlay

**Features:**
- Book library view (list all downloaded books)
- Chapter selection
- Playback controls (play/pause, seek bar, speed, volume)
- Progress indicator (current chapter, time remaining)
- Keyboard shortcuts (space = play/pause, arrows = seek)

---

## Project Structure

```
audiobook/
├── src/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── royal_road.py          # Royal Road scraper
│   │   └── formatter.py           # Text formatting
│   ├── tts/
│   │   ├── __init__.py
│   │   ├── engine.py              # TTS engine wrapper
│   │   ├── annotator.py           # Annotation parser
│   │   └── generator.py           # Audio generation
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py       # Ollama API client
│   │   └── annotation_prompt.py   # Prompt engineering
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py                 # FastAPI app
│   │   ├── models.py              # Database models
│   │   └── routes.py              # API routes
│   └── utils/
│       ├── __init__.py
│       └── config.py              # Configuration management
├── tests/
│   ├── scraper/
│   ├── tts/
│   ├── llm/
│   └── web/
├── data/
│   ├── books/                     # Downloaded books
│   │   └── {book_id}/
│   │       ├── chapters/          # Text files
│   │       ├── audio/             # Audio files
│   │       ├── annotations/       # Annotation JSON
│   │       └── metadata.json      # Book metadata
│   ├── databases/                 # SQLite databases
│   └── checkpoints/               # Test checkpoints
├── web/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── audio/                 # Served audio files
│   └── templates/
│       └── index.html
├── docs/
│   ├── ARCHITECTURE.md
│   └── API.md
├── .archive/
│   └── plans/
├── scripts/                       # Utility scripts
├── Makefile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
├── .env.example
└── README.md
```

---

## Prerequisites & Manual Steps

### System Requirements
- **Python:** 3.10+ (check with `python3 --version`)
- **GPU:** Optional but recommended for TTS (CUDA-compatible)
- **RAM:** 8GB+ (16GB recommended for TTS models)
- **Storage:** 10GB+ free space (for models and audio)

### Manual Steps Required

1. **Install Ollama** (if not already installed)
   - Download from: https://ollama.ai
   - Install and verify: `ollama --version`
   - Pull model: `ollama pull llama3.1:8b` (or mistral:7b)

2. **Install TTS System** (choose one)
   - **Coqui TTS:** `pip install TTS` (will be automated in setup)
   - **Piper TTS:** Download from https://github.com/rhasspy/piper (will be automated)

3. **Get Royal Road Book URL**
   - Navigate to Royal Road book page
   - Copy the book URL (e.g., `https://www.royalroad.com/fiction/12345/book-title`)

---

## Phase Dependencies

```
Phase 1 (Scraper)
    ↓
Phase 2 (TTS) ──→ Phase 4 (Web App)
    ↑
Phase 3 (LLM Annotation)
```

**Dependencies:**
- Phase 2 can start after Phase 1 (needs text files)
- Phase 3 can start after Phase 1 (needs text files)
- Phase 4 needs Phase 2 (needs audio files)
- Phase 3 can enhance Phase 2 (better annotations)

---

## Risk Assessment

### High Risk
1. **Royal Road HTML Structure Changes**
   - **Mitigation:** Robust CSS selectors, fallback parsing, version checkpoints
   - **Detection:** Test suite with golden dataset

2. **TTS Model Quality/Performance**
   - **Mitigation:** Test multiple TTS engines, benchmark before committing
   - **Detection:** Subjective quality tests, performance metrics

3. **LLM Annotation Accuracy**
   - **Mitigation:** Iterative prompt engineering, human validation samples
   - **Detection:** Annotation quality metrics, A/B testing

### Medium Risk
1. **Rate Limiting on Royal Road**
   - **Mitigation:** Respectful delays, retry logic, user-agent rotation
   - **Detection:** Error rate monitoring

2. **Large File Sizes (Audio)**
   - **Mitigation:** Compression options, streaming support
   - **Detection:** File size metrics

3. **Browser Audio API Limitations**
   - **Mitigation:** Fallback to server-side streaming if needed
   - **Detection:** Cross-browser testing

---

## Success Criteria Summary

**Phase 1 Complete When:**
- [ ] Can download 10+ chapters from Royal Road
- [ ] Text extraction >95% clean
- [ ] Error recovery works
- [ ] Golden dataset created

**Phase 2 Complete When:**
- [ ] Audio quality is natural-sounding
- [ ] Annotations affect audio output
- [ ] Processing speed acceptable
- [ ] Golden dataset: text → audio validated

**Phase 3 Complete When:**
- [ ] LLM adds meaningful annotations
- [ ] Original text unchanged
- [ ] Annotation quality validated
- [ ] Golden dataset: text → annotations validated

**Phase 4 Complete When:**
- [ ] All playback controls work
- [ ] Progress tracking persists
- [ ] UI is responsive
- [ ] E2E test: download → annotate → TTS → playback works

---

## Next Steps

1. **Review and approve this plan**
2. **Set up project structure** (Phase 0)
3. **Begin Phase 1** (Royal Road scraper)
4. **Iterate based on metrics**

---

## Notes

- **TTS Model Selection:** Will benchmark Coqui XTTS v2 vs Piper before Phase 2 completion
- **Annotation Format:** May evolve based on TTS engine capabilities
- **Web App Design:** Start simple, add features based on usage
- **Performance:** Optimize for user experience, not theoretical maximums

---

**Plan Version:** 1.0  
**Last Updated:** 2025-01-27

