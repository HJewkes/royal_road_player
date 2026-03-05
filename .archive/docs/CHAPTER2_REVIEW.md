# Chapter 2 Chunks Needing Review

Based on validation of chapter 2 (219 chunks total).

## Summary

From sample validation of first 50 chunks: **27 failed chunks** (<90% similarity)

### Severity Breakdown

- **🔴 Critical (<50% similarity)**: Chunks with severe issues
- **🟡 High (50-85% similarity)**: Chunks with significant issues  
- **🟢 Medium (85-90% similarity)**: Chunks close to threshold

## Top 5 Worst Chunks

### Chunk 25: 19.15% similarity 🔴 CRITICAL
- **Issues**: 
  - "flicked" → "flipped" (word substitution)
  - "quite" → "equate" (mispronunciation)
- **Action**: Regenerate - severe TTS errors

### Chunk 11: 56.55% similarity 🟡 HIGH
- **Issues**:
  - "harries Gooch" → "Harry's gooch" (possessive/verb confusion)
  - "Evergreen" → "Every green" (word splitting)
- **Action**: Regenerate - TTS splitting compound word incorrectly

### Chunk 19: 57.01% similarity 🟡 HIGH
- **Issues**:
  - "I'd" → "I" (missing contraction)
- **Action**: Regenerate - TTS dropping contraction

### Chunk 21: 89.14% similarity 🟢 MEDIUM
- **Issues**:
  - "WibRob" → "Wybrob" (pronunciation)
  - "Banbury" → "Bambri" (pronunciation)
- **Action**: Review - may be acceptable pronunciation variations

### Chunk 3: 99.15% similarity ✅ MINOR
- **Issues**:
  - "Art" → "out" (likely formatting/normalization)
- **Action**: Review - very minor, may be acceptable

## Common Issue Patterns

### Pronunciation Issues (Most Common)
- `carl → karl` (3 occurrences)
- `rushall → russia` (3 occurrences)
- `lyons → lions` (2 occurrences)
- `henri → honry` (2 occurrences)
- `id → i` (2 occurrences - missing contractions)
- `bark → barc` (2 occurrences)
- `rushalls → russias` (1 occurrence)
- `evergeen → evagin` (1 occurrence)
- `flair → flare` (1 occurrence)

### Word Substitutions
- `flicked → flipped`
- `quite → equate`
- `harries → harrys`
- `evergreen → every green`

### Missing/Extra Words
- Missing contractions: `I'd → I`
- Extra words: `green`, `or`, `rout`, `love`, `line`, `hill`, `one`

## Recommendations

1. **Regenerate Critical Chunks**: Chunks 25, 11, 19 need regeneration
2. **Pronunciation Dictionary**: Add corrections for common mispronunciations:
   - `carl → karl`
   - `rushall → russia` 
   - `lyons → lions`
   - `henri → honry`
3. **Review Medium Priority**: Many chunks at 85-90% may be acceptable variations
4. **Full Validation**: Run complete validation for all 219 chunks to get full picture

## Next Steps

1. Run full batch validation for all 219 chunks
2. Regenerate chunks with <85% similarity
3. Add pronunciation corrections for recurring issues
4. Review chunks 85-90% to determine if acceptable

