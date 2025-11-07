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

## Text Preprocessing Recommendations

### 1. **Clean but Preserve Structure**

```python
# Good: Preserve natural formatting
text = """
Chapter 1

The morning sun cast long shadows. James walked slowly.

"I can't believe it," he said.
"""

# XTTS v2 handles this well:
# - Paragraph breaks = natural pauses
# - Punctuation = natural intonation
# - Dialogue = natural speech patterns
```

### 2. **Normalize Whitespace (but keep structure)**

```python
import re

def prepare_text_for_xtts(text: str) -> str:
    """Prepare text for XTTS v2."""
    # Normalize multiple spaces to single space
    text = re.sub(r' +', ' ', text)
    
    # Normalize multiple newlines to double (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Ensure proper spacing around punctuation
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
    
    # Keep paragraph breaks (double newlines)
    # Keep dialogue formatting
    # Keep punctuation
    
    return text.strip()
```

### 3. **Handle Special Cases**

```python
# Numbers - XTTS v2 handles these well
"Chapter 7" → reads as "Chapter seven"
"£800,000" → reads naturally

# Abbreviations - usually fine
"U.K." → reads as "U K" or "United Kingdom"
"Dr. Smith" → reads as "Doctor Smith"

# Markdown formatting - strip but preserve structure
# Your scraper already converts HTML → Markdown
# Markdown formatting (bold, italic) is fine - XTTS ignores it
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

## Conclusion

**For XTTS v2: Use raw, well-formatted text.**

- ✅ Natural punctuation = natural pauses
- ✅ Paragraph breaks = scene pauses  
- ✅ Dialogue formatting = natural speech
- ✅ Global speed/emotion = chapter-level control
- ❌ SSML/annotations = not supported

**Your current text format (Markdown from HTML) is perfect!**

Just ensure:
- Good punctuation
- Paragraph breaks preserved
- Dialogue properly formatted
- No SSML/markup

XTTS v2 will handle the rest naturally.

