# Real TTS Errors Identified

Based on validation of chunks 1-100, here are the **real TTS errors** that need attention (not normalization issues or acceptable variations).

## Important: Truncation vs Word Splitting

Many issues initially classified as "truncation" are actually **word splitting** - TTS is splitting compound words into parts. These can often be fixed with normalization rather than regeneration.

## Word Splitting Errors (Most Common)

These are cases where TTS splits compound words into separate words. **Many can be fixed with normalization:**

### Fixed with Normalization ✅

| Error | Normalized | Status |
|-------|------------|--------|
| `ashtrays` → `ash trays` | `ashtrays` ↔ `ash trays` | ✅ Fixed |
| `doorframe` → `door frame` | `doorframe` ↔ `door frame` | ✅ Fixed |
| `soulmate` → `soul mate` | `soulmate` ↔ `soul mate` | ✅ Fixed |
| `football` → `foot ball` | `football` ↔ `foot ball` | ✅ Fixed |

### Needs Investigation/Regeneration

| Error | Issue | Action |
|-------|-------|--------|
| `earbud` → `air butt` | Split AND mispronounced | 🔴 Regenerate |
| `condescending` → `con-sending` | Split with hyphen | 🟡 Investigate |
| `dingbat` → `ding-buck` | Split with hyphen AND mispronounced | 🔴 Regenerate |

## True Word Truncation Errors

These are cases where TTS is actually cutting off words, losing significant portions:

### Severe Truncation (>50% loss)

| Error | Loss | Missing Portion | Severity | Notes |
|-------|------|-----------------|----------|-------|
| `amour → a` | 80% | "mour" | 🔴 Critical | True truncation - investigate chunk 52 |

### Moderate Truncation (30-50% loss)

| Error | Loss | Missing Portion | Severity | Notes |
|-------|------|-----------------|----------|-------|
| `playdar → play` | 43% | "dar" | 🟡 High | May be splitting |
| `unzipped → unzip` | 38% | "ped" | 🟡 Medium | Past tense loss - may be acceptable |
| `directors → direct` | 33% | "ors" | 🟡 Medium | May be splitting |

## Complete Word Errors

These are cases where TTS completely mispronounces or substitutes words:

| Error | Type | Severity |
|-------|------|----------|
| `soulmate → sole` | Word truncation/error | 🔴 Critical |
| `earbud → the` | Complete substitution | 🔴 Critical |
| `urgent → gurigenty` | Complete mispronunciation | 🔴 Critical |
| `kin → kinnell` | Extra characters added | 🟡 High |

## Analysis

### Patterns Identified

1. **Compound Words**: Many truncations affect compound words:
   - `doorframe`, `football`, `ashtrays`, `playdar`, `dingbat`
   - TTS may be splitting these incorrectly

2. **Word Endings**: Many truncations remove suffixes:
   - `-ing` endings: `condescending`, `unzipped`
   - `-s` endings: `directors`, `ashtrays`
   - May indicate TTS stopping early

3. **Word Boundaries**: Some errors suggest TTS confusion at word boundaries:
   - `soulmate → sole` (may be splitting "soul mate")
   - `earbud → the` (complete confusion)

### Possible Causes

1. **Chunk Boundaries**: Words at end of chunks may be getting cut off
2. **Sentence Splitting**: TTS may be incorrectly splitting compound words
3. **Model Limitations**: XTTS v2 may have issues with certain word patterns
4. **Text Preprocessing**: May need better handling of compound words before TTS

## Recommendations

### Immediate Actions

1. **Regenerate Affected Chunks**: Chunks containing these errors should be regenerated
2. **Investigate Word Positions**: Check if these words are at:
   - End of chunks
   - End of sentences
   - After punctuation
3. **Review Text Preprocessing**: Consider:
   - Adding spaces in compound words before TTS?
   - Better handling of word boundaries?
   - Pronunciation hints for problematic words?

### Long-term Solutions

1. **Pronunciation Dictionary**: Add problematic words to TTS pronunciation dictionary
2. **Chunk Boundary Handling**: Improve padding/processing at chunk boundaries
3. **Compound Word Handling**: Better preprocessing for compound words
4. **Monitoring**: Track these patterns across more chunks to identify systematic issues

## Chunks to Regenerate

Based on validation results, regenerate chunks containing these errors. To find specific chunks:

```bash
# Search for chunks containing these words
grep -r "condescending\|ashtrays\|amour\|doorframe\|football\|playdar\|unzipped\|dingbat\|directors\|soulmate\|earbud\|urgent" data/books/*/chapters/*/chunks/*/text.txt
```

Then regenerate those chunks after investigating the root cause.

