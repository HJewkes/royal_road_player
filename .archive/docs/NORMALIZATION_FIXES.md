# Normalization Fix Recommendations

Based on batch validation of chunks 1-100, here are the normalization fixes needed:

## Issues Found

### 1. Formatting Characters (Asterisks) - HIGH PRIORITY
**Issue**: Asterisks (`*`) are not being removed during normalization
**Examples**:
- `*the → the` (1x)
- `*isnt*. → jisn` (1x) - Also causing transcription error
- `traitors*. → traders` (1x)
- `Missing: *not*` (1x)

**Fix**: Remove asterisks and other formatting characters before comparison

### 2. Parentheses - MEDIUM PRIORITY
**Issue**: Parentheses are not being removed
**Examples**:
- `(whats → whats` (1x)
- `) → shandom` (1x) - Also causing transcription error

**Fix**: Remove parentheses during normalization

### 3. Number Normalization - LOW PRIORITY (May already be working)
**Issue**: Some number words vs digits mismatches
**Examples**:
- `eight → 8` (1x)
- `fifty → 58` (1x) - This looks like a transcription error, not normalization
- `nine → 9` (1x)

**Note**: The normalization already converts digits to words. These may be edge cases or transcription errors.

## Recommended Fixes

### Fix 1: Remove Formatting Characters

Add to `normalize_text()` function in `backend/src/utils/text_comparison.py`:

```python
# Remove formatting characters (asterisks, underscores used for emphasis)
text = re.sub(r'\*+', '', text)  # Remove asterisks
text = re.sub(r'_+', '', text)  # Remove underscores (if used for emphasis)
```

### Fix 2: Remove Parentheses

Add to `normalize_text()` function:

```python
# Remove parentheses (formatting, not content)
text = re.sub(r'[()]', '', text)  # Remove parentheses
```

### Fix 3: Verify Number Normalization

The number normalization should already handle digits → words conversion. The issues may be:
- Edge cases where numbers aren't being matched
- Transcription errors (e.g., "fifty" → "58" is likely a TTS/STT error, not normalization)

## Implementation Priority

1. **HIGH**: Remove asterisks (affects 4+ cases)
2. **MEDIUM**: Remove parentheses (affects 2+ cases)
3. **LOW**: Review number normalization edge cases (may not be needed)

## Testing

After implementing fixes, re-run validation on affected chunks to verify:
```bash
python scripts/batch_validate_chunks.py book_58187 1 --chunks <affected_chunks> --batch-size 25
```

