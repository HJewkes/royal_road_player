# Speaker Detection Research for Audiobook Dialogue

> **Status:** Research Document  
> **Date:** 2025-01-27  
> **Purpose:** Evaluate tools and best practices for speaker detection in novel dialogue

## Executive Summary

After researching existing tools and approaches for speaker detection in books and audiobook generation, **very few open-source solutions exist** that handle dialogue speaker detection in novels. Most existing tools focus on screenplays (which have explicit speaker names) rather than narrative prose with quoted dialogue.

**Key Finding:** The best approach for our use case appears to be **LLM-based speaker detection** using a local model, as it can leverage context and narrative patterns that rule-based approaches cannot handle reliably.

## Existing Tools & Projects

### 1. script-to-speech (Screenplay Parser)

**Repository:** https://github.com/trentw/script-to-speech  
**Language:** Python  
**License:** MIT  
**Stars:** 0 (new project)

**What it does:**
- Converts screenplays (PDF/TXT) into multi-voiced audiobooks
- Uses TTS providers (OpenAI, ElevenLabs, Cartesia, etc.)
- Handles speaker attribution and dialogue parsing

**Approach:**
- **Probabilistic state machine** with indentation-based detection
- Screenplays have explicit speaker names and structured formatting
- Uses regex patterns and indentation heuristics
- Tracks state transitions: TITLE → SCENE_HEADING → ACTION → SPEAKER_ATTRIBUTION → DIALOGUE

**Key Code Pattern:**
```python
class ScreenplayParser:
    def calculate_probabilities(self, line, indentation, current_state, ...):
        # Calculates probability scores for each possible state
        # Uses indentation, patterns, and context
        probs = {state: 0.1 for state in State}
        
        # Dual speaker detection
        if self.is_dual_speaker(line, indentation):
            probs[State.DUAL_SPEAKER_ATTRIBUTION] += 1.0
        
        # Dialogue detection based on indentation
        if indentation in range(dialogue_indent_min, dialogue_indent_max):
            probs[State.DIALOGUE] += 0.8
```

**Relevance to Novels:**
- ❌ **Not directly applicable** - Screenplays have explicit speaker names and structured formatting
- ✅ **Useful concepts:**
  - State machine approach for tracking dialogue context
  - Probabilistic scoring for ambiguous cases
  - Context tracking (previous lines, indentation patterns)

### 2. Coqui TTS Projects

**Found:** Several voice cloning demos using Coqui TTS  
**Relevance:** Low - Focus on voice cloning, not speaker detection

**Key Insight:** Coqui TTS supports speaker embeddings, which could be useful **after** we've identified speakers, but doesn't help with detection.

## Why Screenplay Tools Don't Work for Novels

### Screenplay Format (Structured)
```
JOHN
What are you doing here?

MARY
I came to talk to you.
```

**Characteristics:**
- Explicit speaker names (all caps, indented)
- Clear formatting conventions
- Dialogue blocks are indented consistently
- Minimal narrative text

### Novel Format (Narrative Prose)
```
John walked into the room. "What are you doing here?" he asked.

Mary looked up from her book. "I came to talk to you," she said quietly.
```

**Challenges:**
- Speaker attribution is embedded in narrative text
- Quotation marks indicate dialogue, but speaker is often in surrounding text
- Multiple attribution patterns:
  - `"Dialogue," speaker said.`
  - `Speaker said, "Dialogue."`
  - `"Dialogue," speaker said, "more dialogue."`
  - `"Dialogue."` (no explicit attribution - requires context)
- Pronouns and references require character tracking
- Narrative text between dialogue provides context

## Best Practices & Approaches

### 1. LLM-Based Speaker Detection (Recommended)

**Why it works:**
- LLMs excel at understanding context and narrative patterns
- Can track character references across multiple sentences
- Handles ambiguous cases (pronouns, implied speakers)
- Can learn from examples

**Approach:**
```python
# Pseudo-code for LLM-based detection
def detect_speakers_with_llm(text_chunk: str, context: str) -> List[DialogueChunk]:
    prompt = f"""
    Analyze the following text and identify all dialogue segments with their speakers.
    
    Context from previous text: {context}
    
    Text to analyze:
    {text_chunk}
    
    Return JSON with:
    {{
        "dialogue_segments": [
            {{
                "text": "exact quoted dialogue",
                "speaker": "character name or null if unknown",
                "start_pos": character_position,
                "end_pos": character_position,
                "confidence": 0.0-1.0
            }}
        ]
    }}
    """
    
    response = llm_client.complete(prompt)
    return parse_dialogue_segments(response)
```

**Advantages:**
- ✅ Handles complex narrative patterns
- ✅ Can use context from previous chunks
- ✅ Works with ambiguous cases
- ✅ Can be fine-tuned on your specific book format

**Disadvantages:**
- ❌ Requires LLM API calls (cost/latency)
- ❌ May need prompt engineering for accuracy
- ❌ Requires validation/testing

**Implementation Strategy:**
1. **Chunk text** into manageable sections (e.g., 500-1000 characters)
2. **Include context** from previous chunk (last 200 chars) for continuity
3. **Batch process** multiple chunks for efficiency
4. **Validate results** - check for consistency, handle edge cases
5. **Cache results** - avoid re-processing same text

### 2. Rule-Based Quotation Parsing (Baseline)

**Why it's limited:**
- Can identify quoted dialogue segments
- Cannot reliably determine speaker without context
- Useful as first pass before LLM processing

**Approach:**
```python
import re

def extract_quoted_dialogue(text: str) -> List[QuotedSegment]:
    # Match quoted text with various patterns
    patterns = [
        r'"([^"]+)"',  # Standard double quotes
        r''([^']+)'',  # Single quotes
        r'[""]([^""]+)[""]',  # Smart quotes
    ]
    
    segments = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            segments.append({
                'text': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'full_match': match.group(0)
            })
    
    return segments

def find_speaker_attribution(text: str, dialogue_start: int) -> Optional[str]:
    # Look for attribution patterns before/after dialogue
    # Patterns: "text," speaker said. / Speaker said, "text."
    
    # Check text before quote
    before = text[max(0, dialogue_start-100):dialogue_start]
    attribution_patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|asked|replied|answered|whispered|shouted)',
        r'(?:said|asked|replied|answered)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
    ]
    
    for pattern in attribution_patterns:
        match = re.search(pattern, before, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Check text after quote
    after = text[dialogue_start+len(quote):dialogue_start+len(quote)+100]
    # Similar patterns...
    
    return None
```

**Use Cases:**
- ✅ First pass to identify dialogue segments
- ✅ Pre-processing before LLM analysis
- ✅ Fallback when LLM is unavailable

### 3. Hybrid Approach (Recommended)

**Combine rule-based + LLM:**

1. **Rule-based extraction:**
   - Identify all quoted dialogue segments
   - Extract obvious speaker attributions (explicit "said" patterns)
   - Mark ambiguous cases

2. **LLM processing:**
   - Process ambiguous cases
   - Validate rule-based results
   - Fill in missing speakers using context

3. **Post-processing:**
   - Consistency checking (same character name variations)
   - Character name normalization
   - Confidence scoring

## Implementation Recommendations

### Phase 1: Baseline Quotation Detection

**Goal:** Identify all quoted dialogue segments

**Steps:**
1. Extend `TextChunker` to detect quoted segments
2. Create `DialogueSegment` model with:
   - `text`: The quoted dialogue
   - `start_pos`: Character position in original text
   - `end_pos`: Character position in original text
   - `speaker`: Optional speaker name
   - `confidence`: Confidence score (0.0-1.0)
3. Add quotation detection to chunking pipeline

**Code Structure:**
```python
# backend/src/text_processing/dialogue_detector.py
class DialogueDetector:
    def detect_quoted_segments(self, text: str) -> List[DialogueSegment]:
        """Extract all quoted dialogue segments."""
        pass
    
    def find_speaker_attribution(self, text: str, segment: DialogueSegment) -> Optional[str]:
        """Find speaker attribution for a dialogue segment."""
        pass
```

### Phase 2: LLM-Based Speaker Detection

**Goal:** Use local LLM to identify speakers for dialogue segments

**Steps:**
1. Extend `AnnotationPrompt` class (or create new `DialoguePrompt`)
2. Create prompt template for speaker detection
3. Integrate with existing Ollama client
4. Process chunks with context window

**Code Structure:**
```python
# backend/src/llm/dialogue_prompt.py
class DialoguePrompt:
    SYSTEM_PROMPT = """You are a dialogue analysis assistant for audiobook generation.
    Your task is to identify speakers for quoted dialogue in narrative text.
    Use context from surrounding text to determine who is speaking."""
    
    @staticmethod
    def create_speaker_detection_prompt(
        text: str, 
        dialogue_segments: List[DialogueSegment],
        context: Optional[str] = None
    ) -> str:
        """Create prompt for speaker detection."""
        pass
```

**Integration:**
```python
# backend/src/services/dialogue_service.py
class DialogueService:
    def __init__(self, llm_client: OllamaClient):
        self.llm_client = llm_client
        self.detector = DialogueDetector()
    
    def process_chapter(self, chapter_text: str) -> List[DialogueChunk]:
        # 1. Extract quoted segments
        segments = self.detector.detect_quoted_segments(chapter_text)
        
        # 2. Find obvious speakers (rule-based)
        for segment in segments:
            speaker = self.detector.find_speaker_attribution(chapter_text, segment)
            if speaker:
                segment.speaker = speaker
                segment.confidence = 0.8
        
        # 3. Process ambiguous cases with LLM
        ambiguous = [s for s in segments if not s.speaker]
        if ambiguous:
            speakers = self._detect_with_llm(chapter_text, ambiguous)
            # Update segments with LLM results
        
        return segments
```

### Phase 3: Chunking Integration

**Goal:** Create dialogue-aware chunks for TTS

**Steps:**
1. Modify `TextChunker` to create dialogue chunks
2. Each dialogue chunk should:
   - Contain a single speaker's dialogue
   - Include speaker metadata for voice selection
   - Preserve text positions for audio concatenation
3. Handle mixed chunks (narrative + dialogue)

**Code Structure:**
```python
# backend/src/text_processing/chunker.py (extend existing)
class TextChunker:
    def chunk_with_dialogue(
        self,
        text: str,
        dialogue_segments: List[DialogueSegment],
        ...
    ) -> List[Chunk]:
        """Create chunks that respect dialogue boundaries."""
        # Strategy:
        # 1. Create chunks for each dialogue segment (with speaker)
        # 2. Create chunks for narrative text between dialogue
        # 3. Ensure all chunks respect max_chars limit
        pass
```

## Metrics & Validation

### Success Metrics

1. **Detection Accuracy:**
   - True positive rate: % of dialogue correctly identified
   - False positive rate: % of non-dialogue marked as dialogue
   - Speaker attribution accuracy: % of speakers correctly identified

2. **Coverage:**
   - % of quoted text that gets speaker attribution
   - % of chunks that have speaker metadata

3. **Performance:**
   - Processing time per chapter
   - LLM API calls per chapter
   - Cost per chapter (if using paid LLM)

### Validation Approach

1. **Golden Dataset:**
   - Manually annotate 3-5 chapters with dialogue segments and speakers
   - Use for testing and validation
   - Track accuracy over time

2. **Edge Cases to Test:**
   - Nested quotes (`"He said, 'Hello,' and left."`)
   - Unattributed dialogue (`"Hello."` with no "said" pattern)
   - Multiple speakers in same paragraph
   - Dialogue interrupted by narrative
   - Character name variations (John vs. John Smith vs. Mr. Smith)

## Next Steps

1. **Research Phase (Current):**
   - ✅ Search for existing tools
   - ✅ Document findings
   - ✅ Identify best practices

2. **Prototype Phase:**
   - [ ] Implement baseline quotation detection
   - [ ] Test on sample chapters
   - [ ] Create golden dataset (manual annotation)

3. **LLM Integration:**
   - [ ] Design prompt template
   - [ ] Test with local Ollama model
   - [ ] Validate accuracy on golden dataset

4. **Production Integration:**
   - [ ] Integrate with chunking pipeline
   - [ ] Add speaker metadata to chunks
   - [ ] Update TTS service to use speaker info
   - [ ] Add voice mapping UI

## References

- **script-to-speech:** https://github.com/trentw/script-to-speech
  - Screenplay parser with probabilistic state machine
  - Useful for understanding structured text parsing

- **Current Codebase:**
  - `backend/src/text_processing/chunker.py` - Existing chunking logic
  - `backend/src/llm/annotation_prompt.py` - LLM prompt patterns
  - `backend/src/llm/ollama_client.py` - LLM client implementation

## Conclusion

**Recommended Approach:** Hybrid rule-based + LLM detection

1. **Start with rule-based** quotation detection (fast, reliable for obvious cases)
2. **Use LLM for ambiguous cases** (handles context, pronouns, implied speakers)
3. **Validate and normalize** results (consistency checking, name normalization)

This approach balances **accuracy** (LLM handles complex cases) with **performance** (rule-based handles obvious cases quickly) and **cost** (minimize LLM calls).

The lack of existing tools for novel dialogue detection suggests this is a relatively unexplored area, making our implementation potentially valuable for the open-source community.
