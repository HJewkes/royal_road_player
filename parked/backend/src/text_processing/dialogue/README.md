# Dialogue Extraction Module

This module provides a two-pass LLM approach for extracting dialogue and identifying speakers in narrative text.

## Overview

The dialogue extraction system uses two LLM passes:

1. **Character Identification Pass**: Identifies all characters in a chapter and extracts their traits (both innate and temporary)
2. **Dialogue Extraction Pass**: Extracts all quoted dialogue segments, identifies speakers, and extracts emotion/speed cues

## Architecture

```
dialogue/
├── models.py          # Data models (Character, DialogueSegment, etc.)
├── prompts.py         # LLM prompt templates
├── llm_service.py     # LLM service implementations
├── service.py         # Main DialogueService orchestrator
└── __init__.py        # Module exports
```

## Usage

### Basic Usage

```python
from src.text_processing.dialogue import DialogueService

# Initialize service (creates OllamaClient internally)
service = DialogueService()

# Process a single chapter
chapter_text = '''
John walked into the room. "Hello," he said.
Mary looked up. "Hi there," she replied excitedly.
'''

char_analysis, dialogue_analysis, warnings = service.process_chapter(
    chapter_text=chapter_text,
    chapter_id="chapter_1",
    context_hint="Fantasy novel",
    validate=True,  # Enable validation (default)
)

# Access results
print(f"Found {len(char_analysis.characters)} characters")
print(f"Extracted {len(dialogue_analysis.segments)} dialogue segments")

if warnings:
    print(f"Validation warnings: {len(warnings)}")
    for warning in warnings[:5]:  # Show first 5 warnings
        print(f"  - {warning}")

for segment in dialogue_analysis.segments:
    print(f"Speaker: {segment.speaker}")
    print(f"Text: {segment.text}")
    if segment.emotion:
        print(f"Emotion: {segment.emotion.emotion}")
    if segment.speed:
        print(f"Speed: {segment.speed.speed}")
```

### Processing Multiple Chapters

```python
# Process multiple chapters (maintains character registry)
chapters = [
    ("ch1", "Chapter 1 text..."),
    ("ch2", "Chapter 2 text..."),
    ("ch3", "Chapter 3 text..."),
]

results = service.process_multiple_chapters(
    chapters=chapters,
    context_hint="Fantasy novel",
    validate=True,  # Enable validation (default)
)

# Access results (each entry includes warnings)
for chapter_id, (char_analysis, dialogue_analysis, warnings) in results.items():
    print(f"Chapter {chapter_id}: {len(warnings)} validation warnings")

# Access character registry
registry = service.get_character_registry()
all_characters = registry.get_all_characters()
```

### Accessing Character Information

```python
# Get character by name
john = registry.get_character("John Smith")

# Get characters for a specific chapter
chapter_chars = registry.get_characters_for_chapter("ch1")

# Access character traits
for char in all_characters:
    print(f"{char.name}:")
    print(f"  Innate traits: {[t.name for t in char.get_innate_traits()]}")
    print(f"  Temporary traits: {[t.name for t in char.get_temporary_traits()]}")
    print(f"  Aliases: {char.aliases}")
```

## Models

### Character

Represents a character with traits and aliases:

```python
Character(
    name="John Smith",
    aliases=["John", "Mr. Smith"],
    traits=[
        CharacterTrait(name="old", category=TraitCategory.INNATE),
        CharacterTrait(name="excited", category=TraitCategory.TEMPORARY),
    ],
)
```

### DialogueSegment

Represents a single dialogue segment:

```python
DialogueSegment(
    text="Hello, how are you?",
    speaker="John Smith",
    start_pos=100,
    end_pos=120,
    emotion=EmotionCue(emotion="excited", intensity=0.8),
    speed=SpeedCue(speed="fast", multiplier=1.2),
    confidence=0.9,
)
```

## Two-Pass Approach

### Pass 1: Character Identification

The first pass analyzes the chapter text to:
- Identify all characters mentioned
- Extract innate traits (age, nationality, accent, etc.)
- Extract temporary traits (emotional state, physical condition, etc.)
- Track character aliases and nicknames
- Merge with characters from previous chapters

**Prompt Strategy:**
- Provides context from previous chapters (for character continuity)
- Asks LLM to differentiate between innate and temporary traits
- Requests confidence scores for uncertain identifications

### Pass 2: Dialogue Extraction

The second pass extracts dialogue segments:
- Identifies all quoted text
- Determines speaker for each segment
- Extracts emotion/mood cues
- Extracts speed/pacing cues
- Uses character information from first pass

**Prompt Strategy:**
- Provides character list from first pass
- Includes context from adjacent chapters (for continuity)
- Asks for emotion and speed cues based on context
- Requests accurate character positions

## Integration with Existing Code

The dialogue module can be integrated with the existing chunking system:

```python
from src.text_processing.dialogue import DialogueService
from src.text_processing.chunker import TextChunker

# Extract dialogue first
dialogue_service = DialogueService()
char_analysis, dialogue_analysis = dialogue_service.process_chapter(
    chapter_text=text,
    chapter_id=chapter_id,
)

# Then chunk with dialogue awareness
chunker = TextChunker()
chunks = chunker.chunk_by_paragraphs(
    text=text,
    # Can use dialogue_analysis.segments to inform chunking
)
```

## Configuration

The service uses the existing Ollama client configuration:

- `OLLAMA_BASE_URL`: Base URL for Ollama API (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model name to use (default: from settings)

Temperature can be adjusted per call (default: 0.3 for more consistent results):

```python
service.process_chapter(
    chapter_text=text,
    chapter_id=chapter_id,
    temperature=0.5,  # Higher = more creative, lower = more consistent
)
```

## Error Handling

The service handles errors gracefully:
- If LLM call fails, returns empty analysis
- Logs errors for debugging
- Continues processing even if individual chapters fail

## Validation

The service includes built-in validation to prevent LLM hallucinations:

### Dialogue Validation

- **Text Matching**: All dialogue segments must match word-for-word with quoted text in the original
- **Position Validation**: Segment positions are validated against the original text
- **Quote Detection**: Only text that is actually quoted in the original is accepted

### Character Validation

- **Mention Detection**: All characters must be mentioned by name or alias in the chapter
- **Speaker Validation**: Dialogue speakers must match identified characters
- **Alias Matching**: Characters can be found by their aliases/nicknames

### Validation Behavior

- Invalid dialogue segments are filtered out
- Invalid characters are filtered out
- Invalid speakers are removed (segment kept but speaker set to None)
- Warnings are returned for all validation issues
- Validation can be disabled with `validate=False`

### Example

```python
char_analysis, dialogue_analysis, warnings = service.process_chapter(
    chapter_text=text,
    chapter_id="ch1",
    validate=True,  # Default
)

# Check for validation issues
if warnings:
    print("Validation warnings:")
    for warning in warnings:
        print(f"  - {warning}")

# Only validated results are returned
# Invalid items are filtered out automatically
```

## Testing

The dialogue module is fully testable without requiring a running LLM. All unit tests use mocked LLM clients.

### Running Tests

```bash
# Run all dialogue tests (uses mocks, no LLM required)
pytest tests/text_processing/test_dialogue*.py -v

# Run only unit tests
pytest tests/text_processing/test_dialogue*.py -m unit -v

# Run with coverage
pytest tests/text_processing/test_dialogue*.py --cov=src.text_processing.dialogue --cov-report=term
```

### Using MockOllamaClient

For testing, use `MockOllamaClient` instead of the real `OllamaClient`:

```python
from src.text_processing.dialogue.service import DialogueService
from src.text_processing.dialogue.test_utils import (
    MockOllamaClient,
    create_mock_character_response,
    create_mock_dialogue_response,
)

# Create mock responses
char_response = create_mock_character_response([
    {
        "name": "John Smith",
        "aliases": ["John"],
        "traits": [{"name": "old", "category": "innate", "confidence": 1.0}],
        "first_mentioned": True,
    }
])

dialogue_response = create_mock_dialogue_response([
    {
        "text": "Hello",
        "speaker": "John Smith",
        "start_pos": 0,
        "end_pos": 5,
        "confidence": 0.9,
    }
])

# Create service with mock client
mock_client = MockOllamaClient(responses=[char_response, dialogue_response])
service = DialogueService(llm_client=mock_client)

# Use service normally - no real LLM calls
char_analysis, dialogue_analysis, warnings = service.process_chapter(
    chapter_text='John said "Hello"',
    chapter_id="test_ch1",
    validate=False,
)
```

### Test Structure

- **Unit Tests**: Fast, isolated tests using `MockOllamaClient` (marked with `@pytest.mark.unit`)
- **Integration Tests**: Optional tests with real LLM (marked with `@pytest.mark.integration`)
- **Validation Tests**: Test validation logic independently (no LLM required)

### Integration Tests (Real LLM)

To run integration tests with a real LLM:

```bash
# 1. Ensure Ollama is running
ollama serve

# 2. Set environment variable
export OLLAMA_AVAILABLE=true

# 3. Run integration tests
pytest tests/text_processing/test_dialogue_integration.py -v

# Or run all tests (unit + integration)
pytest tests/text_processing/test_dialogue*.py -v
```

Integration tests automatically skip if Ollama is not available.

See [DIALOGUE_TESTING.md](../../../docs/DIALOGUE_TESTING.md) for detailed testing documentation.

## Future Enhancements

Potential improvements:
- Caching LLM responses for repeated processing
- Batch processing for efficiency
- Fine-tuning prompts based on book genre
- Integration with voice mapping system
- Persistence of character registry across sessions
- Configurable validation strictness levels
