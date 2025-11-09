# ebook2audiobook - Key Learning Opportunities

**Quick Reference:** Top opportunities to adopt from ebook2audiobook

---

## 🎯 Top 3 High-Value Opportunities

### 1. M4B Output Format with Chapter Markers ⭐⭐⭐

**Why:** Industry standard audiobook format, better player compatibility

**What to do:**
- Use FFmpeg to create M4B files with embedded chapter markers
- Generate chapter metadata file for FFmpeg
- Preserve chapter boundaries in audio output

**Implementation:**
```python
# Generate FFmpeg chapter metadata
def generate_chapter_metadata(chapters, output_path):
    """Generate FFmpeg chapter metadata file"""
    with open(output_path, 'w') as f:
        for i, chapter in enumerate(chapters):
            start_time = chapter['start_time']
            end_time = chapter['end_time']
            f.write(f"[CHAPTER]\n")
            f.write(f"TIMEBASE=1/1000\n")
            f.write(f"START={int(start_time * 1000)}\n")
            f.write(f"END={int(end_time * 1000)}\n")
            f.write(f"title={chapter['title']}\n\n")

# FFmpeg command
ffmpeg -i input.wav -i chapters.txt \
    -map 0 -map_metadata 1 \
    -codec:a aac -b:a 128k \
    output.m4b
```

**Priority:** High | **Effort:** Medium | **Impact:** High

---

### 2. Fine-Tuned Model Support ⭐⭐⭐

**Why:** Significantly better voice quality, access to 40+ pre-trained voices

**What to do:**
- Create model registry for fine-tuned XTTSv2 models
- Support custom model uploads (ZIP files)
- Integrate with HuggingFace model hub
- Add voice preview/selection UI

**Implementation Pattern:**
```python
# Model registry
FINE_TUNED_MODELS = {
    "DavidAttenborough": {
        "repo": "drewThomasson/fineTunedTTSModels",
        "sub": "xtts-v2/eng/DavidAttenborough/",
        "voice_ref": "voices/DavidAttenborough.wav",
        "language": "eng",
    },
    # ... more models
}

# Custom model upload
def upload_custom_model(zip_path, required_files):
    """Validate and extract custom model ZIP"""
    # Check required files exist
    # Extract to model directory
    # Register in model registry
```

**Priority:** High | **Effort:** High | **Impact:** Very High

---

### 3. Docker Deployment with GPU Support ⭐⭐⭐

**Why:** Easier deployment, better GPU support, multi-platform compatibility

**What to do:**
- Create multi-stage Dockerfile
- Support multiple PyTorch variants (CUDA 11.8, 12.1, CPU, ROCm)
- Add Docker Compose configuration
- Pre-download models in Docker build

**Implementation:**
```dockerfile
# Multi-stage build with PyTorch variants
ARG TORCH_VERSION="cuda118"
FROM pytorch/pytorch:${TORCH_VERSION} AS base

# Install dependencies
RUN pip install -r requirements.txt

# Pre-download models
RUN python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

**Priority:** High | **Effort:** Medium | **Impact:** High

---

## 🟡 Medium Priority Opportunities

### 4. Session Management System

**Why:** Better progress tracking, resume capability, cancellation support

**Key Pattern:**
- Use `multiprocessing.Manager()` for shared state
- Session-based job tracking
- Resume interrupted conversions

**Priority:** Medium | **Effort:** Medium | **Impact:** Medium

---

### 5. TTS Engine Caching & Memory Management

**Why:** Faster subsequent requests, better memory usage, support concurrent jobs

**Key Pattern:**
- Global cache dictionary for loaded engines
- Memory-aware unloading (`max_tts_in_memory = 2`)
- Thread-safe loading with locks

**Priority:** Medium | **Effort:** Low | **Impact:** Medium

---

### 6. EPUB/MOBI Input Support

**Why:** Broader use case, support for any ebook source

**Key Pattern:**
- Use `ebooklib` for EPUB parsing
- Use Calibre for format conversion
- Extract metadata and chapter structure

**Priority:** Medium | **Effort:** High | **Impact:** High (but expands scope)

---

## 🟢 Low Priority (Nice to Have)

### 7. Multi-Language Support
- Support 1100+ languages via Fairseq MMS
- Language-specific text processing
- **Priority:** Low (we're focused on English)

### 8. Audio Quality Controls
- Normalization, silence trimming
- Background noise detection
- **Priority:** Low (can add post-processing later)

### 9. Gradio Admin Interface
- Quick prototyping tool
- Admin dashboard
- **Priority:** Low (we have React UI)

---

## Quick Wins (Easy to Implement)

1. **Audio Format Options** - Add M4B, MP3, FLAC output formats
2. **Chapter Markers** - Generate FFmpeg chapter metadata
3. **Model Registry** - Create registry for fine-tuned models
4. **Docker Support** - Basic Dockerfile with GPU support
5. **Session Tracking** - Add session IDs to job queue

---

## Implementation Roadmap

### Phase 1: Audio Format & Quality (2-3 weeks)
- [ ] M4B output format with chapter markers
- [ ] Multiple output format support (MP3, FLAC, M4B)
- [ ] Audio normalization

### Phase 2: Model Support (3-4 weeks)
- [ ] Fine-tuned model registry
- [ ] Custom model upload support
- [ ] Voice preview/selection UI

### Phase 3: Deployment (2-3 weeks)
- [ ] Dockerfile with GPU support
- [ ] Docker Compose configuration
- [ ] Multi-stage builds for PyTorch variants

### Phase 4: Advanced Features (4-6 weeks)
- [ ] Session management system
- [ ] TTS engine caching
- [ ] EPUB/MOBI input support (optional)

---

## Code Patterns to Adopt

### Session Management
```python
from multiprocessing import Manager

manager = Manager()
sessions = manager.dict()

def get_session(id):
    if id not in sessions:
        sessions[id] = manager.dict({
            "status": None,
            "progress": 0,
            "cancellation_requested": False,
        })
    return sessions[id]
```

### Model Registry
```python
MODELS = {
    "default": {
        "repo": "coqui/XTTS-v2",
        "sub": "",
    },
    "david_attenborough": {
        "repo": "drewThomasson/fineTunedTTSModels",
        "sub": "xtts-v2/eng/DavidAttenborough/",
    }
}
```

### TTS Engine Caching
```python
loaded_tts = {}

def get_tts_engine(model_key):
    if model_key not in loaded_tts:
        loaded_tts[model_key] = load_model(model_key)
    return loaded_tts[model_key]

def unload_unused_engines(keys_to_keep):
    keys_to_remove = [k for k in loaded_tts.keys() if k not in keys_to_keep]
    for key in keys_to_remove:
        del loaded_tts[key]
        torch.cuda.empty_cache()
```

---

## References

- **Full Analysis:** [EBOOK2AUDIOBOOK_ANALYSIS.md](./EBOOK2AUDIOBOOK_ANALYSIS.md)
- **Source Repository:** https://github.com/DrewThomasson/ebook2audiobook
- **Fine-Tuned Models:** https://huggingface.co/drewThomasson/fineTunedTTSModels
