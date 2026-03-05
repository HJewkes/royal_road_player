# Text Formatting Analysis - TTS Readability

This document analyzes all formatting patterns in the book that might affect TTS quality.

## Summary

- **Tables found**: 4 unique tables (all converted successfully ✅)
- **Other patterns identified**: Several formatting patterns that may need normalization
- **Current status**: Most patterns are handled, but some may benefit from enhancement

## Tables

### Confirmed Tables

All 4 tables have been extracted and tested. See `docs/TABLE_CONVERSION_REPORT.md` for details:

1. **Chapter 02** - Full league table (top 4 teams)
2. **Chapter 04** - Full league table (top 4 teams)  
3. **Chapter 08** - Partial league table (bottom 5 teams)
4. **Chapter 11** - Partial league table (bottom 5 teams)

All tables convert successfully to natural-sounding prose.

## Other Formatting Patterns

### 1. Dash-Separated Numbers (133 occurrences)

**Pattern**: `\d+-\d+-\d+` (e.g., `3-5-2`, `4-4-2`)

**Examples**:
- "We played a 3-5-2 formation."
- "I gave him a confused smile. 'I don't want perfection. I just want them to do what I want. It's dead simple. 4-4-2, 5-4-1, 4-5-1.'"

**TTS Impact**: ✅ **GOOD** - These are football formations and read naturally as "three-five-two", "four-four-two", etc.

**Recommendation**: No changes needed.

---

### 2. Slash Ratios (1 occurrence)

**Pattern**: `\d+/\d+` (e.g., `21/53`, `18/155`)

**Example**:
```
Bea Pea started the day on CA 30 (out of 36), Julie was 21/53, and Angel 18/155.
```

**TTS Impact**: ⚠️ **POTENTIALLY PROBLEMATIC** - "21/53" reads as "twenty-one slash fifty-three" which is awkward. These appear to be current/max values (like "21 out of 53").

**Current Behavior**: Passes through unchanged: "Julie was 21/53, and Angel 18/155."

**Recommendation**: ✅ **IMPLEMENTED** - Normalized to "21 out of 53" for better readability.

---

### 3. Colon Ratios (1 occurrence)

**Pattern**: `\d+:\d+` (e.g., `7:58`)

**Example**:
```
I checked. 7:58. "Yeah, I'm here. I'm ready."
```

**TTS Impact**: ✅ **GOOD** - Time format reads naturally as "seven fifty-eight".

**Recommendation**: No changes needed.

---

### 4. Percentages (31 occurrences)

**Pattern**: `\d+%` (e.g., `110%`, `27%`, `97%`)

**Examples**:
- "110% effort"
- "27% are FOMO Followers"
- "97% of the time"

**TTS Impact**: ✅ **GOOD** - Percentages read naturally.

**Recommendation**: No changes needed.

---

### 5. Repeated Punctuation (13 occurrences)

**Pattern**: `[!?]{2,}` (e.g., `!!!!`, `?!`)

**Examples**:
- "GOOOOAAAALLLL!!!!"
- "He did WHAT?!"

**Current Behavior**: Normalizer converts `!!!!` to `! ! !` (spaces between exclamation marks).

**TTS Impact**: ✅ **ACCEPTABLE** - Spacing helps TTS engines handle repeated punctuation better.

**Recommendation**: Current handling is fine.

---

### 6. All Caps Acronyms (94 occurrences)

**Pattern**: `\b[A-Z]{3,}\b` (e.g., `WSL`, `VIP`, `SILK`)

**Examples**:
- "WSL quality"
- "VIP access"
- "SILK smooth"

**TTS Impact**: ✅ **GOOD** - Acronyms are typically handled well by TTS engines (read as individual letters or as words if they're common acronyms).

**Recommendation**: No changes needed.

---

### 7. Mixed Case Acronyms (59 occurrences)

**Pattern**: `\b[A-Z][a-z]+[A-Z][a-z]+\b` (e.g., `PlayStation`, `WibWob`)

**Examples**:
- "PlayStation"
- "WibWob"

**TTS Impact**: ✅ **GOOD** - These are proper nouns/brand names and read naturally.

**Recommendation**: No changes needed.

---

## Recommendations

### High Priority

1. ✅ **Slash Ratios** - **IMPLEMENTED** - Normalizes `21/53` → `21 out of 53`
   - Only 1 occurrence found in book, but now handles all future occurrences
   - Context suggests these are "current/max" values
   - Dates (DD/MM/YYYY) are protected and handled separately by date normalizer

### Low Priority / Monitoring

1. **Formation Numbers** - Monitor if any unusual formations appear that might confuse TTS
2. **Repeated Punctuation** - Current handling is acceptable, but could be refined if needed

### No Action Needed

- Dash-separated numbers (formations)
- Colon ratios (times)
- Percentages
- Acronyms (all caps and mixed case)
- Repeated punctuation (current normalization works)

## Test Coverage

All tables are covered by test suite:
- `backend/tests/text_processing/test_table_converter_book_tables.py`
- `backend/tests/text_processing/book_tables.json`

## Future Enhancements

If slash ratios become more common, consider adding normalization:

```python
# In normalizer.py
def normalize_slash_ratios(self, text: str) -> str:
    """Convert slash ratios to natural language.
    
    Examples:
        21/53 -> 21 out of 53
        18/155 -> 18 out of 155
    """
    # Pattern: number/number (but not dates like 12/25/2024)
    pattern = r'(\d+)/(\d+)(?![0-9])'  # Not followed by another digit
    return re.sub(pattern, r'\1 out of \2', text)
```

