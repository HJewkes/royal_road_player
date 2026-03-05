# TTS Normalization Review - Chapter by Chapter Analysis

This document provides a comprehensive review of all text patterns in the book that may need normalization or pronunciation hints for optimal TTS quality.

## Executive Summary

**Total Chapters Reviewed**: 16  
**Key Findings**:
- ✅ Most formatting patterns are already handled well
- ⚠️ A few patterns may benefit from pronunciation hints or normalization
- 📊 No critical issues found that would significantly impact TTS quality

## Patterns Already Handled ✅

### 1. Tables (4 occurrences)
- **Status**: ✅ Fully handled
- **Implementation**: Converted to natural language prose
- **See**: `docs/TABLE_CONVERSION_REPORT.md`

### 2. Slash Ratios (1 occurrence)
- **Status**: ✅ Fully handled
- **Implementation**: `21/53` → `21 out of 53`
- **Example**: "Julie was 21/53" → "Julie was 21 out of 53"

### 3. Formations (133+ occurrences)
- **Status**: ✅ Reads naturally
- **Examples**: `3-5-2`, `4-4-2`, `4-1-4-1`
- **TTS**: Reads as "three-five-two", "four-four-two", etc.
- **Recommendation**: No changes needed

### 4. Repeated Punctuation (8 occurrences)
- **Status**: ✅ Handled by normalizer
- **Example**: `GOOOOAAAALLLL!!!!` → Normalized to spaced punctuation
- **Recommendation**: Current handling is acceptable

### 5. Percentages (31 occurrences)
- **Status**: ✅ Reads naturally
- **Examples**: `110%`, `27%`, `97%`
- **TTS**: Reads as "one hundred ten percent", "twenty-seven percent"
- **Recommendation**: No changes needed

### 6. Ellipsis (305 occurrences)
- **Status**: ✅ Handled by normalizer
- **Implementation**: `...` → `…` (ellipsis character)
- **Recommendation**: Current handling is fine

## Patterns That May Need Attention ⚠️

### 1. CA/PA Values (60 occurrences)

**Pattern**: `CA 30`, `PA 155`, `CA 90`, etc.

**Context**: These are game mechanics (Current Ability / Potential Ability) from the football management game.

**Examples**:
- "Bea Pea started the day on CA 30 (out of 36)"
- "At CA 90 he was one of the better players"
- "PA 155 future star"

**Current Behavior**: Read as "C A 30", "P A 155" (acronyms)

**Recommendation**: 
- ✅ **As long as read as acronyms (C-A, P-A), that's fine**
- ⚠️ **Monitor STT validation** - If TTS reads as "Saa" or "Pa" (words), add pronunciation hints
- **Priority**: Low (monitor via STT validation)

**Chapters Affected**: 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16

---

### 2. Technical Acronyms (105 occurrences)

**Pattern**: `CA`, `PA`, `FOMO`, `WSL`, `VIP`, `BTTS`

**Examples**:
- "Five of these are WSL quality" (Women's Super League)
- "27% are FOMO Followers" (Fear Of Missing Out)
- "VIP access"

**Current Behavior**: Read as individual letters or as words if TTS engine recognizes them

**Recommendation**:
- **WSL**: Could expand to "Women's Super League" on first mention
- **FOMO**: Could expand to "Fear Of Missing Out" on first mention
- **VIP**: Reads fine as "V I P" or "vip"
- **CA/PA**: See above
- **Priority**: Low (most are clear from context)

**Chapters Affected**: All chapters

---

### 3. Single-Letter Abbreviations (20 occurrences) ✅ IMPLEMENTED

**Pattern**: `B. R`, `H. W`, `O. B`, `T. W`, `J. I`, etc.

**Examples**:
- "William B. Roberts" → "William B Roberts"
- "Andrew H. We don't need" → "Andrew H We don't need"
- "Clivie O. But look" → "Clivie O But look"

**Implementation**: ✅ **Normalized** - Periods removed from single-letter abbreviations
- `B. ` → `B ` (prevents impacting sentence splitting logic)
- Preserves multi-letter abbreviations (Dr., Mr., U.S., etc.)
- `fix_punctuation_spacing` updated to detect and preserve abbreviations

**Current Behavior**: Read as "B R", "H W", etc. (no period)

**Priority**: ✅ **Complete** - Periods removed to avoid splitting issues

**Chapters Affected**: 1, 2, 3, 4, 5, 7, 8, 11, 12, 13, 14, 15

---

### 4. Foreign Characters (15 occurrences)

**Pattern**: Accented characters: `é`, `ö`, `ã`, `ä`, `í`, `è`

**Examples**:
- "Rolf Fringer" (with accented characters)
- "Schrödinger's cat" (ö)
- "Mbappé celebration" (é)

**Current Behavior**: Should be handled correctly by TTS engines

**Recommendation**: 
- Monitor TTS output for correct pronunciation
- Most TTS engines handle accented characters well
- **Priority**: Low (test with actual TTS to verify)

**Chapters Affected**: 4, 7, 12, 13, 15, 16

---

### 5. Brand Names / Mixed Case (37 occurrences)

**Pattern**: `PowerPoint`, `YouTube`, `TikTok`, `AirBnB`, `WhatsApp`, `McKay`, `McNally`

**Examples**:
- "put them on our YouTube and TikTok"
- "Tell us about your AirBnB"
- "Julie McKay"

**Current Behavior**: Should read naturally (brand names are typically well-handled)

**Recommendation**:
- Most TTS engines handle brand names correctly
- **Priority**: Very Low (test if needed)

**Chapters Affected**: 1, 3, 4, 5, 6, 8, 10, 11, 12, 13, 15, 16

---

### 6. Hyphenated Names (13 occurrences)

**Pattern**: `Smith-Smithe`, `Amadi-Spokes`, `Two-Thumbs`, `No-Wins`, `Post-It`

**Examples**:
- "Smith-Smithe," I said
- "Caine Amadi-Spokes fell to the floor"
- "Maxy No-Handshake"

**Current Behavior**: Should read naturally with hyphen pause

**Recommendation**:
- TTS engines typically handle hyphens well
- **Priority**: Very Low (test if needed)

**Chapters Affected**: 1, 6, 9, 10, 11, 14, 16

---

### 7. Complex Dialogue (1043 occurrences)

**Pattern**: Multiple quote marks in single lines (dialogue with nested quotes)

**Example**:
```
"Top. As Grimsby manager I don't accept your resignation. On behalf of the people of Grimsby, I don't accept your resignation."
```

**Current Behavior**: Handled by normalizer (quotes converted to curly quotes)

**Recommendation**:
- Current handling is fine
- **Priority**: None (this is normal fiction formatting)

---

## Recommendations Summary

### High Priority
**None** - All critical patterns are already handled.

### Medium Priority
**None** - Current handling is acceptable.

### Low Priority
1. **CA/PA Values** - Consider adding pronunciation hints if TTS reads them awkwardly
2. **Technical Acronyms** - Consider expanding on first mention (WSL, FOMO)

### Very Low Priority
1. **Single-letter abbreviations** - Character nicknames, context makes clear
2. **Foreign characters** - Test with TTS to verify pronunciation
3. **Brand names** - Should be fine, test if needed
4. **Hyphenated names** - Should be fine, test if needed

## Testing Recommendations

1. **Generate test audio** for chapters with:
   - CA/PA values (Chapter 8, 9, 12, 15)
   - Technical acronyms (Chapter 3, 11)
   - Foreign characters (Chapter 4, 12, 13)

2. **Listen for**:
   - Awkward pauses in acronyms
   - Mispronounced foreign names
   - Unclear abbreviations

3. **If issues found**, implement:
   - Acronym expansion dictionary
   - Pronunciation hints for specific terms
   - Custom normalization rules

## Implementation Notes

### If Adding Acronym Expansion

Create a configuration file:
```python
# In normalizer config
acronym_expansions = {
    'CA': 'Current Ability',
    'PA': 'Potential Ability',
    'WSL': 'Women\'s Super League',
    'FOMO': 'Fear Of Missing Out',
    'VIP': 'Very Important Person',
    'BTTS': 'Both Teams To Score',
}
```

### If Adding Pronunciation Hints

Use SSML or similar:
```xml
<phoneme alphabet="ipa" ph="ˈkʌrənt əˈbɪlɪti">CA</phoneme>
```

## Conclusion

The text is **well-formatted** for TTS generation. The existing normalization handles:
- ✅ Tables (converted to prose)
- ✅ Slash ratios (normalized to "out of")
- ✅ Formations (read naturally)
- ✅ Punctuation (normalized)
- ✅ Dates and numbers (normalized)

**No critical issues** were found that would significantly impact TTS quality. The patterns identified are mostly:
- Game-specific terminology (CA/PA) that may be familiar to readers
- Character names and nicknames (context makes clear)
- Brand names (typically well-handled by TTS)

**Recommendation**: Proceed with current normalization. Test audio output and add pronunciation hints only if specific issues are identified during listening.

