# XTTS v2 Text Preparation Guide

## Key Finding: **Use Raw, Well-Formatted Text**

XTTS v2 does **NOT** support SSML or markup annotations. However, it handles **natural text formatting** very well and has some built-in controls.

## What XTTS v2 Supports

### ✅ Built-in Parameters

1. **Speed Control** (`speed` parameter)
   - Range: 0.5 - 2.0 (default: 1.0)
   - Global speed adjustment for entire text
   - Example: `speed=1.2` for 20% faster

2. **Emotion Control** (`emotion` parameter)
   - Options: `neutral`, `happy`, `sad`, `angry`, `surprised`, `fearful`, `disgusted`
   - Global emotion for entire text
   - Example: `emotion="happy"`

3. **Emotion Cues in Text** (experimental)
   - Can use brackets: `[happy]`, `[sad]`, `[angry]`
   - May work for emotion changes mid-text
   - Example: `"Hello [happy] world [sad] goodbye"`

4. **Sentence Splitting** (`split_sentences=True` by default)
   - Automatically splits on punctuation
   - Handles natural pauses well
   - Respects sentence boundaries

### ❌ What XTTS v2 Does NOT Support

- SSML markup
- Fine-grained pause control (millisecond-level)
- Per-word emphasis
- Pitch control via text
- Speed changes mid-text (only global)
- Custom prosody annotations

## Best Practices for Text Preparation

### ✅ DO: Use Natural Text Formatting

**Good Examples:**

```text
The morning sun cast long shadows across the empty street. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.

He had been waiting for this moment for weeks, and now it was finally here.
```

**Why this works:**
- Natural punctuation (periods, commas, question marks)
- Paragraph breaks create natural pauses
- Proper sentence structure
- XTTS v2's `split_sentences=True` handles this well

### ✅ DO: Use Punctuation for Pacing

```text
"Wait," he said. "What did you say?"

She paused. Then, slowly: "I said... nothing."
```

**Punctuation creates natural pauses:**
- `.` = sentence pause
- `,` = short pause
- `?` = question intonation
- `!` = exclamation intonation
- `...` = longer pause
- `:` = pause before explanation

### ✅ DO: Use Paragraph Breaks for Scene Changes

```text
The door slammed shut.

[New paragraph = natural pause]

James found himself alone in the dark room.
```

### ✅ DO: Preserve Dialogue Formatting

```text
"I can't believe it," Max said.

Henri replied, "Neither can I."
```

**Why:** XTTS v2 handles dialogue naturally with proper punctuation.

### ❌ DON'T: Add SSML or Markup

```text
<!-- BAD -->
<speak>
  <prosody rate="slow">Hello</prosody>
  <break time="500ms"/>
  world
</speak>

<!-- XTTS v2 will read this literally! -->
```

### ❌ DON'T: Over-Format Text

```text
<!-- BAD -->
Hello...world...with...too...many...dots

<!-- BAD -->
Hello    world    with    too    many    spaces
```

**Why:** XTTS v2 may interpret these literally or awkwardly.

## Text Preprocessing Pipeline

### Complete Normalization Pipeline

The system implements a comprehensive normalization pipeline (`src/tts/normalizer.py`) that handles:

#### 1. **Punctuation Normalization**

```python
# Normalize quotes to curly quotes
"He said 'hello'" → "He said 'hello'"

# Convert -- to em-dash
"He was tired -- very tired" → "He was tired — very tired"

# Collapse repeated punctuation
"Hello!!!" → "Hello!"

# Canonicalize ellipsis
"Wait..." → "Wait…"
```

#### 2. **Acronym Expansion**

```python
# Expand acronyms with word-boundary checks
"FC" → "F. C." (in context: "Millwall FC" → "Millwall F. C.")
"U.K." → "United Kingdom" (if configured)
"Dr." → "Doctor" (if configured)

# Case-sensitive expansion
"FC" (all caps) → "F. C."
"Fc" (mixed case) → may not expand (depends on rules)
```

#### 3. **Number & Currency Normalization**

```python
# Ages
"28-year-old" → "twenty-eight-year-old" (spoken as "twenty-eight year old")

# Currency (configurable style)
"£800,000" → "eight hundred thousand pounds" (words style)
"£800,000" → "eight hundred thousand pounds" (default)

# Large numbers
"1,234,567" → "one million, two hundred thirty-four thousand, five hundred sixty-seven"
```

#### 4. **Date Normalization**

```python
# Various date formats → spoken form
"4 Feb, 2024" → "the fourth of February, twenty-twenty-four"
"04/02/2024" → "the fourth of February, twenty-twenty-four" (locale-aware)
"Sunday, 4 Feb, 2024" → "Sunday, the fourth of February, twenty-twenty-four"
```

#### 5. **Whitespace & Paragraph Normalization**

```python
# Collapse excess spaces
"Hello    world" → "Hello world"

# Preserve blank lines as paragraph separators
"Paragraph 1\n\nParagraph 2" → preserved

# Normalize multiple newlines
"\n\n\n" → "\n\n" (paragraph break)
```

**Usage:**

```python
from src.tts.normalizer import normalize

# With default rules
paragraphs = normalize(raw_text)

# With custom rules
rules = {
    'acronym_map': {'FC': 'F. C.', 'U.K.': 'United Kingdom'},
    'number_style': 'words',
    'date_style': 'spoken',
    'preserve_paragraphs': True
}
paragraphs = normalize(raw_text, rules)
```

### Breath-Group Segmentation

For natural prosody, text should be segmented into breath-groups (speakable phrases). The system implements this in `src/tts/segmenter.py`:

#### Segmentation Heuristics

```python
# Dialogue quotes become separate segments
"I can't believe it," he said. → ["I can't believe it,", "he said."]

# Split on long commas when clause exceeds max_chars_per_breath (~180-220 chars)
"He was not a morning person at the best of times, and I had snatched him out of bed" 
→ ["He was not a morning person at the best of times,", "and I had snatched him out of bed"]

# Split at em-dashes (asides/interruptions)
"He walked — slowly — to the door" → ["He walked —", "slowly —", "to the door"]

# Parenthetical/semicolon boundaries
"He paused; then continued." → ["He paused;", "then continued."]
```

#### Segment Metadata

Each segment includes metadata:

```python
Segment(
    id="deterministic_hash",
    text="ready-for-synthesis text",
    meta={
        "is_dialogue": True,
        "speaker_hint": "Max",
        "pacing": "slow"  # from DSL tags
    }
)
```

**Usage:**

```python
from src.tts.segmenter import segment, segment_all

# Segment single paragraph
segments = segment(paragraph, cfg={'max_chars_per_breath': 200})

# Segment all paragraphs
all_segments = segment_all(paragraphs, cfg={'max_chars_per_breath': 200})
```

### Micro-SSML DSL (Inline Tags)

While XTTS v2 doesn't support SSML, the system implements a lightweight DSL (`src/tts/dsl_parser.py`) that maps to XTTS-compatible actions:

#### Supported Tags

```text
[voice=Name]          → Switch active voice until changed or paragraph ends
[pause:500]           → Timeline pause of 500 milliseconds (implemented during stitching)
[slow]...[/slow]      → Pacing hint: shorter segments + ellipses for slower cadence
[fast]...[/fast]      → Pacing hint: tighter phrasing for faster cadence
[epigraph]...[/epigraph] → Style marker: pre/post pauses + slower cadence
[scene-break] or ***  → Scene separator: pause length from style policy (default 900ms)
[say-as="TEXT"]       → Replace token with TEXT before segmentation
```

#### Parsing Rules

1. **Case-insensitive**: `[VOICE=Name]` = `[voice=Name]`
2. **Nesting**: Only `[slow]/[fast]` within `[epigraph]` allowed
3. **Conflicts**: Outermost tag wins
4. **Unknown tags**: Ignored (sanitized)

#### Example Usage

```text
[epigraph][slow]"No one likes us, we don't care."[/slow] Millwall F. C. fans.[/epigraph]

The morning sun cast long shadows.

[voice=Henri]"I can't believe it,"[/voice] Henri said.

[voice=Narrator]He walked slowly to the door.[/voice]

***

[scene-break]

[voice=Max]"Wait,"[/voice] Max paused. [pause:300] "What did you say?"
```

#### Mapping to XTTS v2

- **Pauses**: Implemented during stitching (insert silence of specified ms)
- **Pacing**: Emulated via segmentation (shorter segments + ellipses for slow, tighter for fast)
- **Voice**: Resolved to `speaker_wav` path via voice registry at plan time
- **Scene breaks**: Insert pause (default 900ms) during stitching

**Usage:**

```python
from src.tts.dsl_parser import parse_dsl
from src.tts.dsl_mapper import map_dsl_to_segments

# Parse DSL tags
dsl_output = parse_dsl(text_with_dsl_tags)  # Returns list[Segment | Event]

# Map to segments with voice resolution
voice_registry = load_voice_registry()
mapped_items = map_dsl_to_segments(dsl_output, voice_registry, default_voice)
```

### Planning & Voice Resolution

The system converts segments/events into synthesis plans:

#### ChunkPlan Structure

```python
ChunkPlan(
    id="deterministic_hash",  # SHA1 of {chapter_index, seq, voice_name, text}
    text="ready-for-synthesis text",
    voice_name="british_male",  # Logical voice ID
    speaker_wav="/path/to/reference.wav",  # Resolved path
    language="en",
    pacing="slow",  # Optional: "slow" | "fast" | None
    neighbor_context="previous 120 chars"  # For context-aware prosody
)
```

#### Voice Resolution Rules

1. **Active voice**: Maintained per segment (default: narrator)
2. **Voice switching**: `[voice=Name]` updates active voice until changed
3. **Registry lookup**: Logical name → `{speaker_wav, language}` from voice registry
4. **Fallback**: If voice not found, use default narrator voice

#### Planning Contract

```python
from src.tts.dsl_mapper import map_dsl_to_segments

# Convert segments/events to ChunkPlans
plans = plan(events_and_segments, voice_registry, style_policy)
# Returns: list[ChunkPlan | Event]
```

### Stitching & Timeline Realization

After synthesis, chunks are stitched together with intentional pauses:

#### Stitching Process

```python
# Concatenate chunk WAVs in order
stitched_audio = concatenate([
    chunk_001.wav,
    silence(500ms),  # From [pause:500] event
    chunk_002.wav,
    silence(900ms),  # From [scene-break] event
    chunk_003.wav
])

# Add chapter head/tail room tone
final_audio = add_head_tail_room_tone(
    stitched_audio,
    head_ms=500,  # Default head silence
    tail_ms=1000  # Default tail silence
)
```

#### Timeline Events

Events are inserted during stitching:

- **Pause events**: `Event(kind="pause", ms=500)` → Insert 500ms silence
- **Scene breaks**: `Event(kind="scene_break", ms=900)` → Insert 900ms silence
- **Epigraph**: `Event(kind="epigraph_start")` → Pre-pause + slower cadence
- **Voice switches**: `Event(kind="voice_switch")` → Track for metadata only

**Contract:**

```python
stitch(
    timeline: list[ChunkPlan | Event],
    rendered: dict[str, str],  # {chunk_id: path_to_wav}
    head_ms: int = 500,
    tail_ms: int = 1000
) -> str  # Returns path to stitched chapter WAV
```

### Mastering Targets

For audiobook-quality output, apply mastering:

#### Mastering Parameters

```python
master(
    in_wav: str,
    target_rms_dbfs: float = -20.0,  # Target loudness (audiobook standard)
    max_true_peak_dbfs: float = -3.0,  # Peak limit
    out_wav: str | None = None,
    out_mp3: str | None = None
) -> dict  # Returns {"wav": path, "mp3": optional_path, "gain_db": applied_gain}
```

#### Mastering Process

1. **Loudness normalization**: Adjust RMS to target (-20 dBFS for audiobooks)
2. **Peak limiting**: Ensure peak ≤ -3 dBFS (headroom)
3. **Head/tail room tone**: Add consistent silence (500-1000ms)

**Note**: Mastering is currently a future enhancement. Current chunks are generated without mastering.

### Quality Control (QC) & Regeneration

Detect audio defects and regenerate only defective spans:

#### QC Checks

```python
qc(
    audio_wav: str,
    timeline: list[ChunkPlan | Event]
) -> QCReport  # Returns {items: list[dict], regen_ids: list[str]}
```

**Checks:**

1. **Clipping**: Peak beyond target or near-zero headroom
2. **Excess silence**: Gap > threshold (e.g., 2.5s) not requested by pause event
3. **Truncation**: Trailing partial phoneme artifacts (last 150ms has burst then EOF)

**Example QC Report:**

```json
{
  "items": [
    {
      "chunk_id": "chunk_005",
      "issue": "clipping",
      "details": {"peak_dbfs": -0.5, "threshold": -3.0}
    },
    {
      "chunk_id": "chunk_012",
      "issue": "excess_silence",
      "details": {"gap_ms": 3500, "threshold": 2500}
    }
  ],
  "regen_ids": ["chunk_005", "chunk_012"]
}
```

**Regeneration Process:**

```python
# Re-synthesize only flagged chunks
for chunk_id in qc_report.regen_ids:
    chunk_plan = find_chunk_plan(chunk_id, timeline)
    regenerate_chunk(chunk_plan)

# Re-stitch with regenerated chunks
stitch(timeline, updated_rendered_chunks)
```

**Note**: QC is currently a future enhancement. Current system relies on manual flagging via UI.

### Idempotence & Caching

Enable reproducible builds and caching:

#### Deterministic IDs

```python
# Chunk IDs based on stable hash
chunk_id = sha1(f"{chapter_index}_{seq}_{voice_name}_{text}").hexdigest()

# Include normalization rules hash in ID seed
rules_hash = sha1(json.dumps(normalization_rules, sort_keys=True)).hexdigest()
chunk_id = sha1(f"{chapter_index}_{seq}_{voice_name}_{text}_{rules_hash}").hexdigest()
```

#### Caching Strategy

```python
# Before synthesis, check for existing files
chunk_path = output_dir / f"{chunk_id}.wav"
if chunk_path.exists():
    # Reuse existing chunk (unless rules changed)
    if verify_chunk_validity(chunk_id, rules_hash):
        return chunk_path  # Skip synthesis

# Generate new chunk
generate_chunk(chunk_plan)
```

#### Manifest

Persist manifest with:

```json
{
  "chapter_index": 1,
  "normalization_rules_hash": "abc123...",
  "voice_registry_hash": "def456...",
  "chunks": {
    "chunk_001": {"id": "abc...", "path": "chunk_001.wav", "status": "completed"},
    "chunk_002": {"id": "def...", "path": "chunk_002.wav", "status": "pending"}
  }
}
```

**Benefits:**

- Reproducible builds (same input → same output)
- Incremental regeneration (only changed chunks)
- Cache validation (detect rule/config changes)

### Complete Pipeline Example

```python
# 1. Normalize
paragraphs = normalize(raw_text, rules)

# 2. Parse DSL (if present)
dsl_output = parse_dsl(text_with_dsl)

# 3. Segment into breath-groups
segments = segment_all(paragraphs, cfg)

# 4. Plan synthesis
plans = plan(segments + events, voice_registry, style_policy)

# 5. Synthesize chunks (with caching)
rendered = {}
for plan_item in plans:
    if isinstance(plan_item, ChunkPlan):
        chunk_id = plan_item.id
        if not chunk_exists(chunk_id):
            wav_path = synthesize_chunk(plan_item)
            rendered[chunk_id] = wav_path
        else:
            rendered[chunk_id] = get_existing_chunk_path(chunk_id)

# 6. Stitch with pauses
stitched_path = stitch(plans, rendered, head_ms=500, tail_ms=1000)

# 7. Master (future)
mastered_path = master(stitched_path, target_rms_dbfs=-20.0)

# 8. QC (future)
qc_report = qc(mastered_path, plans)
if qc_report.regen_ids:
    regenerate_and_restitch(qc_report.regen_ids)
```

## Using Emotion and Speed Parameters

### Global Speed Control

```python
# Faster narration (1.2x speed)
engine.synthesize(
    text=text,
    output_path=output_path,
    speaker=speaker_ref,
    language="en",
    speed=1.2,  # 20% faster
)

# Slower, dramatic narration (0.9x speed)
engine.synthesize(
    text=text,
    output_path=output_path,
    speaker=speaker_ref,
    language="en",
    speed=0.9,  # 10% slower
)
```

### Global Emotion Control

```python
# Happy/upbeat chapter
engine.synthesize(
    text=text,
    output_path=output_path,
    speaker=speaker_ref,
    language="en",
    emotion="happy",
)

# Dramatic/serious chapter
engine.synthesize(
    text=text,
    output_path=output_path,
    speaker=speaker_ref,
    language="en",
    emotion="sad",  # or "angry" for intensity
)
```

### Emotion Cues in Text (Experimental)

```python
# Try emotion cues mid-text
text_with_emotion = """
Hello world. [happy] This is exciting! [neutral] But then things changed. [sad] It was over.
"""

# Note: This is experimental and may not work consistently
```

## Comparison: Annotations vs Raw Text

### With Annotations (Future Phase 3)

```json
{
  "text": "Hello world",
  "annotations": [
    {"type": "pause", "position": 5, "duration_ms": 500},
    {"type": "emphasis", "position": 6, "strength": 1.5}
  ]
}
```

**Status:** Not supported by XTTS v2. Would need:
- Post-processing (split audio, apply effects)
- Different TTS engine (Piper supports SSML)
- Custom implementation

### With Raw Text (Current - Recommended)

```text
Hello... world!

[Natural punctuation and formatting]
```

**Status:** ✅ Works great! XTTS v2 handles this naturally.

## Recommendations

### For Your Audiobook Project:

**1. Use Raw, Well-Formatted Text** ✅
- Your scraper already converts HTML → Markdown
- Markdown formatting is fine (XTTS ignores markup)
- Preserve paragraph breaks
- Preserve punctuation
- Preserve dialogue formatting

**2. Text Preprocessing (Optional)**
- Normalize whitespace
- Ensure proper spacing around punctuation
- Keep paragraph breaks (double newlines)
- Remove any SSML/markup if present

**3. Use Global Parameters**
- Set `speed` for chapter pacing (0.9-1.2 range)
- Set `emotion` for chapter tone (if needed)
- Use consistent reference voice

**4. Test Different Text Formats**
- Try with/without extra paragraph breaks
- Try different punctuation styles
- See what sounds most natural

## Example: Optimal Text Format

```text
Chapter 7.1 - The First Cut is the Deepest

The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.

He had been waiting for this moment for weeks, and now it was finally here.

"I can't believe it," Max said, his voice barely a whisper.

Henri replied, "Neither can I. This changes everything."

The football match would begin in an hour, and he could already hear the crowd gathering.
```

**Why this works:**
- Clear chapter title
- Paragraph breaks for scene changes
- Natural punctuation
- Dialogue properly formatted
- No markup or annotations needed

## Future: LLM-Based Text Enhancement (Phase 3)

While XTTS v2 doesn't support annotations, you can still use LLM to:

1. **Improve Text Structure** (without annotations)
   - Add natural paragraph breaks
   - Improve punctuation for better pacing
   - Enhance dialogue formatting
   - Fix awkward phrasing

2. **Suggest Text Improvements**
   - "Add a pause here" → Add `...` or paragraph break
   - "Emphasize this" → Use punctuation or formatting
   - "Slow down here" → Use longer sentences, more commas

3. **Post-Processing** (if needed)
   - Split audio at natural points
   - Apply speed changes to segments
   - Add pauses between segments
   - Rejoin audio

## Practical Example: Complete Text Transformation

### Input Text (Raw from Royal Road)

```text
Chapter 7.1 - The First Cut is the Deepest

"No one likes us, we don't care." Millwall FC fans.

The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.

He was not a morning person at the best of times, and I had snatched him 
out of bed at 6 AM on a Sunday, 4 Feb, 2024.

"I can't believe it," Max said, his voice barely a whisper. He was a 
28-year-old player who had just signed for £800,000.

Henri replied, "Neither can I. This changes everything."

***

[Scene break]

The football match would begin in an hour.
```

### Step 1: Normalization

```python
from src.tts.normalizer import normalize

rules = {
    'acronym_map': {'FC': 'F. C.'},
    'number_style': 'words',
    'date_style': 'spoken'
}

paragraphs = normalize(raw_text, rules)
```

**Result:**

```text
Chapter 7.1 - The First Cut is the Deepest

"No one likes us, we don't care." Millwall F. C. fans.

The morning sun cast long shadows across the empty street in Manchester. 
James walked slowly, his footsteps echoing in the quiet neighbourhood.

He was not a morning person at the best of times, and I had snatched him 
out of bed at six A M on a Sunday, the fourth of February, twenty-twenty-four.

"I can't believe it," Max said, his voice barely a whisper. He was a 
twenty-eight-year-old player who had just signed for eight hundred thousand pounds.

Henri replied, "Neither can I. This changes everything."

***

[Scene break]

The football match would begin in an hour.
```

### Step 2: DSL Parsing (if tags present)

```python
from src.tts.dsl_parser import parse_dsl

# If text contains DSL tags like [voice=Max] or [pause:500]
dsl_output = parse_dsl(normalized_text)
# Returns: list[Segment | Event]
```

### Step 3: Breath-Group Segmentation

```python
from src.tts.segmenter import segment_all

segments = segment_all(paragraphs, cfg={'max_chars_per_breath': 200})
```

**Result:** Text split into speakable phrases with metadata:

```python
[
    Segment(text='"No one likes us, we don\'t care."', meta={'is_dialogue': True}),
    Segment(text='Millwall F. C. fans.', meta={'is_dialogue': False}),
    Segment(text='The morning sun cast long shadows...', meta={'is_dialogue': False}),
    # ... more segments
]
```

### Step 4: Planning & Voice Resolution

```python
from src.tts.dsl_mapper import map_dsl_to_segments
from src.tts.voice_registry import load_voice_registry

voice_registry = load_voice_registry()
plans = map_dsl_to_segments(segments + events, voice_registry, default_voice)
```

**Result:** ChunkPlans with resolved voice paths:

```python
[
    ChunkPlan(
        id="abc123...",
        text='"No one likes us, we don\'t care."',
        voice_name="narrator",
        speaker_wav="/path/to/british_male_p241.wav",
        language="en"
    ),
    # ... more plans
]
```

### Step 5: Synthesis (Current Implementation)

```python
# Current system chunks at paragraph breaks, respects 250-char limit
# Each chunk synthesized separately with XTTS v2
chunks = generate_chapter_chunked(
    text_path,
    chunk_duration_minutes=1.0,
    speaker="british_male"
)
```

### Step 6: Stitching (Future Enhancement)

```python
# Future: Stitch chunks with pauses from events
stitched_path = stitch(plans, rendered_chunks, head_ms=500, tail_ms=1000)
```

### Step 7: Mastering (Future Enhancement)

```python
# Future: Normalize loudness and peak
mastered_path = master(stitched_path, target_rms_dbfs=-20.0, max_true_peak_dbfs=-3.0)
```

### Step 8: Quality Control (Future Enhancement)

```python
# Future: Detect defects and regenerate
qc_report = qc(mastered_path, plans)
if qc_report.regen_ids:
    regenerate_and_restitch(qc_report.regen_ids)
```

## Implementation Status

### ✅ Currently Implemented

- **Normalization**: Full pipeline (`src/tts/normalizer.py`)
  - Punctuation, acronyms, numbers, dates, whitespace
- **Basic Segmentation**: Paragraph-based (`src/tts/chunker.py`)
  - Respects XTTS v2 250-char limit
  - Splits paragraphs → sentences → words if needed
- **DSL Parsing**: Prototype (`src/tts/dsl_parser.py`, `dsl_mapper.py`)
  - Tags detected and parsed
  - Voice resolution via registry
  - Pacing hints extracted
- **Voice Registry**: Complete (`src/tts/voice_registry.py`)
  - Logical names → speaker_wav paths
  - Default voice fallback
- **Chunking**: Production-ready (`src/tts/generator.py`)
  - Deterministic chunk IDs (based on text + position)
  - Metadata tracking (text positions, status, generation times)
  - Incremental generation support

### 🔄 Future Enhancements

- **Breath-Group Segmentation**: Advanced segmentation (`src/tts/segmenter.py` exists but not fully integrated)
  - Dialogue-aware splitting
  - Em-dash/aside detection
  - Configurable max_chars_per_breath
- **Stitching**: Audio concatenation with pauses
  - Insert silences from pause events
  - Scene break pauses
  - Head/tail room tone
- **Mastering**: Loudness normalization
  - RMS target (-20 dBFS)
  - Peak limiting (-3 dBFS)
  - Consistent head/tail silence
- **Quality Control**: Automated defect detection
  - Clipping detection
  - Excess silence detection
  - Truncation detection
  - Automatic regeneration

## Best Practices Summary

### ✅ DO

1. **Use Normalization Pipeline**
   ```python
   from src.tts.normalizer import normalize
   paragraphs = normalize(raw_text, rules)
   ```

2. **Respect 250-Char Limit**
   - Current chunker enforces this automatically
   - Splits paragraphs → sentences → words if needed

3. **Use DSL Tags Sparingly**
   - Only when needed for voice switching or pacing
   - Prefer natural text formatting when possible

4. **Preserve Paragraph Structure**
   - Paragraph breaks = natural pauses
   - Double newlines = scene breaks

5. **Use Deterministic Chunk IDs**
   - Enables caching and incremental regeneration
   - Current system implements this

### ❌ DON'T

1. **Don't Use SSML**
   - XTTS v2 doesn't support it
   - Use DSL tags or natural formatting instead

2. **Don't Exceed 250 Chars Per Chunk**
   - Current system enforces this, but be aware

3. **Don't Over-Segment**
   - Let XTTS v2 handle natural pauses
   - Only segment when needed for voice switching

4. **Don't Skip Normalization**
   - Numbers, dates, acronyms should be normalized
   - Improves pronunciation quality

## Conclusion

**For XTTS v2: Use normalized, well-formatted text with optional DSL tags.**

- ✅ Normalization pipeline = better pronunciation
- ✅ Natural punctuation = natural pauses
- ✅ Paragraph breaks = scene pauses  
- ✅ Dialogue formatting = natural speech
- ✅ DSL tags = voice switching & pacing hints
- ✅ Global speed/emotion = chapter-level control
- ✅ Deterministic chunking = caching & incremental generation
- ❌ SSML = not supported (use DSL instead)

**Current Implementation:**

The system provides a solid foundation with normalization, chunking, and DSL parsing. Future enhancements (stitching, mastering, QC) will complete the pipeline for production-quality audiobooks.

**Your current text format (Markdown from HTML) works great!**

Just ensure:
- Normalize numbers, dates, acronyms
- Good punctuation
- Paragraph breaks preserved
- Dialogue properly formatted
- Use DSL tags only when needed

XTTS v2 + the preprocessing pipeline will handle the rest naturally.

