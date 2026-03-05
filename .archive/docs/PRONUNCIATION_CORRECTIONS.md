# Pronunciation Correction System

## Problem

TTS engines (especially XTTS v2) sometimes mispronounce or incorrectly split words:

- **Word Splitting**: `"amour"` → `"a more"` (French word split into English words)
- **Compound Word Splitting**: `"soulmate"` → `"sole mate"` (compound word split incorrectly)
- **Mispronunciation**: `"earbud"` → `"air butt"` (phonetic mispronunciation)
- **Hyphen Splitting**: `"condescending"` → `"con-sending"` (word split with hyphen)

## Solution

Implemented a **pronunciation correction dictionary** that preprocesses text before TTS generation.

### Approach

1. **Hyphenation**: Forces word boundaries to prevent splitting
   - `"amour"` → `"ah-moor"` (phonetic spelling + hyphenation)
   - `"soulmate"` → `"soul-mate"` (compound word hyphenation)

2. **Phonetic Spelling**: Guides pronunciation for foreign/uncommon words
   - `"amour"` → `"ah-moor"` (French pronunciation guide)

3. **Syllable Separation**: Prevents incorrect word splitting
   - `"condescending"` → `"con-de-scend-ing"` (syllable boundaries)

### Implementation

**File:** `backend/src/utils/text_preprocessing.py`

- `PRONUNCIATION_CORRECTIONS`: Dictionary mapping problematic words to corrected forms
- `correct_pronunciations()`: Function that applies corrections using word boundaries
- Integrated into `preprocess_text_for_tts()` pipeline

### Current Corrections

```python
PRONUNCIATION_CORRECTIONS = {
    # French words
    'amour': 'ah-moor',
    
    # Compound words
    'soulmate': 'soul-mate',
    'earbud': 'ear-bud',
    'earbuds': 'ear-buds',
    'dingbat': 'ding-bat',
    'dingbats': 'ding-bats',
    
    # Words that get split
    'condescending': 'con-de-scend-ing',
}
```

### Usage

The corrections are automatically applied during TTS preprocessing:

```python
from src.utils.text_preprocessing import preprocess_text_for_tts

text = "He found his soulmate and fell in amour."
corrected = preprocess_text_for_tts(text)
# Result: "He found his soul-mate and fell in ah-moor."
```

### Adding New Corrections

To add a new correction, update `PRONUNCIATION_CORRECTIONS`:

```python
PRONUNCIATION_CORRECTIONS = {
    # ... existing entries ...
    'problematic_word': 'corrected-form',
}
```

**Guidelines:**
- Use hyphens to force word boundaries: `"word"` → `"wor-d"` or `"word-part"`
- Use phonetic spelling for foreign words: `"café"` → `"ka-fay"`
- Use syllable separation for long words: `"extraordinary"` → `"ex-tra-or-di-nar-y"`
- Test with actual TTS generation to verify improvement

### Testing

```bash
# Test pronunciation corrections
python -c "from src.utils.text_preprocessing import correct_pronunciations; print(correct_pronunciations('amour'))"
# Output: "ah-moor"
```

### Limitations

- **Case-insensitive**: Corrections apply regardless of capitalization
- **Whole words only**: Uses word boundaries to avoid partial matches
- **Manual maintenance**: New issues must be manually added to dictionary
- **May affect normalization**: Hyphenated words may affect text comparison in validation

### Future Enhancements

1. **Context-aware corrections**: Different corrections based on context
2. **Phonetic dictionary**: Use IPA or CMU phonetic dictionary
3. **LLM-assisted detection**: Use LLM to identify pronunciation issues automatically
4. **Voice-specific corrections**: Different corrections for different TTS voices
5. **Learning from validation**: Automatically add corrections based on validation failures

## Related Files

- `backend/src/utils/text_preprocessing.py` - Pronunciation correction implementation
- `backend/src/tts/engine.py` - TTS engine that uses preprocessing
- `docs/REAL_TTS_ERRORS.md` - Documented TTS errors that led to this system

