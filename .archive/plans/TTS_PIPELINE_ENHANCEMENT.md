# TTS Pipeline Enhancement Plan

## Overview
Enhance TTS pipeline with text normalization, breath-group segmentation, multi-voice infrastructure, and micro-SSML DSL prototype. Audio mastering/QC deferred to later phase.

## Phase 1: Text Normalization ✅ COMPLETED

### 1.1 Normalization Module
**File:** `src/tts/normalizer.py`

Implemented deterministic normalization functions:
- Punctuation normalization (quotes, dashes, ellipsis)
- Acronym expansion (rule-based with word boundaries)
- Number normalization (ages, currency)
- Date normalization (spoken form)
- Whitespace normalization (preserves paragraphs)

### 1.2 Normalization Rules Configuration
**File:** `src/tts/normalization_rules.py`

Configurable rule sets with defaults and file loading support.

### 1.3 Integration
**Updated:** `src/tts/text_preprocessor.py`
- Added `normalize_text()` function
- Preserves existing `prepare_text_for_xtts` for backward compatibility

## Phase 2: Breath-Group Segmentation ✅ COMPLETED

### 2.1 Segmentation Module
**File:** `src/tts/segmenter.py`

Implemented breath-group segmentation:
- Dialogue detection
- Breath-group splitting (commas, em-dashes, semicolons)
- Speaker hint extraction
- Deterministic segment IDs

### 2.2 Segmentation Configuration
**File:** `src/tts/segmentation_config.py`

Configurable parameters (max_chars_per_breath, split preferences).

### 2.3 Integration
**Updated:** `src/tts/chunker.py`
- Added `chunk_segments_by_paragraphs()` for segment-based chunking
- Added `chunk_text_with_segmentation()` function
- Preserves existing paragraph-based chunking

## Phase 3: Multi-Voice Infrastructure ✅ COMPLETED

### 3.1 Voice Registry
**File:** `src/tts/voice_registry.py`

Voice registry system:
- Voice definition (name, speaker_wav, language)
- Registry loading from YAML/JSON
- Default voice fallback
- Voice resolution

### 3.2 Voice Registry Configuration
**File:** `data/voices/default_voices.yaml`

Default narrator voice configuration.

### 3.3 Generator Integration
**Updated:** `src/tts/generator.py`
- Voice registry loading
- Default voice assignment
- Infrastructure ready for multi-voice expansion

## Phase 4: Micro-SSML DSL Prototype ✅ COMPLETED

### 4.1 DSL Parser
**File:** `src/tts/dsl_parser.py`

Basic micro-SSML parser:
- `[voice=Name]` - voice switching
- `[pause:MS]` - timeline pauses
- `[slow]...[/slow]`, `[fast]...[/fast]` - pacing hints
- `[epigraph]...[/epigraph]` - style markers
- `[scene-break]` or `***` - scene separators

### 4.2 DSL Mapper
**File:** `src/tts/dsl_mapper.py`

DSL to XTTS mapping:
- Voice resolution
- Pacing adjustments
- Event preservation

### 4.3 Integration
**Updated:** `src/tts/generator.py`
- DSL detection and parsing
- Voice assignment from DSL
- Event tracking (for future stitching)

## Phase 5: LLM-Assisted Preprocessing 🔄 FUTURE

### 5.1 LLM Speaker Attribution
**Goal:** Use local LLM to identify speakers in dialogue and add `[voice=Name]` tags automatically.

**Use Cases:**
- Resolve ambiguous references ("He said" → identify who)
- Multiple speakers in one paragraph
- Indirect speech attribution
- Character name extraction from context

**Implementation:**
- Create `src/llm/speaker_attribution.py`
- Use Ollama with Llama 3.1 8B or similar
- Prompt engineering for speaker identification
- Add `[voice=Name]` tags to text before DSL parsing

**Contract:**
```python
def identify_speakers(text: str, character_list: Optional[list[str]] = None) -> str
# Returns text with [voice=Name] tags added
```

### 5.2 LLM Semantic Segmentation Hints
**Goal:** Use LLM to suggest natural pause points and breath-group boundaries.

**Use Cases:**
- Identify semantic clause boundaries
- Suggest emotional/intentional pauses
- Better handling of complex sentences
- Context-aware segmentation

**Implementation:**
- Create `src/llm/segmentation_hints.py`
- LLM suggests pause points
- Convert to `[pause:MS]` tags or segmentation hints
- Optional enhancement to rule-based segmentation

**Contract:**
```python
def suggest_pauses(text: str) -> list[dict]  # [{position: int, duration_ms: int, reason: str}]
```

### 5.3 LLM Context-Aware Normalization
**Goal:** Use LLM for ambiguous normalization cases.

**Use Cases:**
- Context-aware acronym expansion ("FC" in "Chester FC" vs "FC Barcelona")
- Ambiguous date/number interpretation
- Domain-specific terminology handling

**Implementation:**
- Create `src/llm/normalization_assistant.py`
- LLM resolves ambiguous cases
- Fallback to rule-based if LLM unavailable
- Cache results for performance

**Contract:**
```python
def normalize_ambiguous(text: str, ambiguous_tokens: list[str]) -> str
# Returns text with ambiguous tokens normalized
```

### 5.4 LLM DSL Tag Suggestion
**Goal:** Use LLM to suggest where DSL tags should be added.

**Use Cases:**
- Suggest `[pause:500]` at dramatic moments
- Suggest `[slow]` for contemplative passages
- Suggest `[voice=Character]` for dialogue
- Suggest `[epigraph]` markers

**Implementation:**
- Create `src/llm/dsl_suggestion.py`
- LLM analyzes text and suggests tags
- User can review/accept/reject suggestions
- Integrates with DSL parser

**Contract:**
```python
def suggest_dsl_tags(text: str) -> str
# Returns text with suggested DSL tags added (marked as suggestions)
```

### 5.5 Integration Strategy
**Approach:** Hybrid preprocessing pipeline

```python
# Optional LLM preprocessing step
def llm_preprocess(text: str, use_speaker_attribution: bool = True) -> str:
    """Use LLM to enhance text before rule-based processing."""
    enhanced = text
    
    if use_speaker_attribution:
        enhanced = identify_speakers(enhanced)
    
    # Other LLM enhancements...
    
    return enhanced

# Then use existing rule-based pipeline
normalized = normalize(llm_preprocessed_text, rules)
segments = segment_all(normalized, config)
```

**Benefits:**
- LLM handles semantic/ambiguous cases
- Rule-based handles deterministic cases (fast, reliable)
- Best of both worlds

**Performance Considerations:**
- LLM preprocessing is slower (can be done offline)
- Cache LLM results for repeated chapters
- Make LLM steps optional/configurable
- Use checkpoint/resume for long texts

## Deferred Features

- Audio stitching/concatenation
- Audio mastering (RMS, peak normalization)
- Quality control and regeneration
- Full multi-voice character assignment (infrastructure ready)
- Advanced DSL features

## Success Criteria

✅ **Phase 1-4 Complete:**
- Normalization working for numbers, dates, acronyms
- Segmentation creating natural breath-groups
- Voice registry infrastructure in place
- DSL prototype parsing basic tags

🔄 **Phase 5 (Future):**
- LLM correctly identifies speakers in dialogue (>90% accuracy)
- LLM suggests useful pause points
- LLM handles ambiguous normalization cases
- LLM suggests relevant DSL tags
- Performance acceptable (can be done offline/preprocessing)

## Notes

- All phases maintain backward compatibility
- Rule-based approaches are fast and deterministic
- LLM assistance adds value for semantic/ambiguous cases
- LLM preprocessing can be done offline and cached
- Infrastructure is ready for multi-voice expansion

