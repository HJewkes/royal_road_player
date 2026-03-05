# Chunks Requiring Manual Review

Based on validation of chunks 1-100, here are chunks that need manual review.

## Critical Priority (<50% similarity)

These chunks have severe issues and require immediate attention:

| Chunk | Similarity | Issue | Action |
|-------|------------|-------|--------|
| 14 | 0.00% | Quote mark only - formatting issue | Review text file |
| 52 | 12.16% | `amour → a` (truncation) | 🔴 Regenerate |
| 58 | 45.88% | Multiple issues | 🔴 Investigate |
| 66 | 60.54% | Multiple issues | 🔴 Investigate |

## High Priority (50-85% similarity)

These chunks have significant issues:

| Chunk | Similarity | Issue | Action |
|-------|------------|-------|--------|
| 27 | 70.00% | Multiple issues | 🟡 Investigate |
| 47 | 76.27% | Multiple issues | 🟡 Investigate |
| 92 | 76.72% | Multiple issues | 🟡 Investigate |
| 28 | 85.78% | Multiple issues | 🟡 Investigate |
| 64 | 86.26% | Multiple issues | 🟡 Investigate |
| 19 | 86.91% | Multiple issues | 🟡 Investigate |
| 20 | 87.42% | Multiple issues | 🟡 Investigate |
| 41 | 89.45% | Multiple issues | 🟡 Investigate |

## Medium Priority (85-90% similarity)

These chunks pass validation but have notable issues:

| Chunk | Similarity | Known Issue | Action |
|-------|------------|-------------|--------|
| 3 | 98.80% | `soulmate → sole mate` (normalized) | ✅ Acceptable |
| 15 | 95.91% | `earbud → air butt` (mispronunciation) | 🔴 Regenerate |
| 36 | 98.19% | `condescending → con-sending` | 🟡 Investigate |
| 57 | 97.47% | `doorframe → door frame` (normalized) | ✅ Acceptable |
| 60 | 97.45% | `football → foot ball` (normalized) | ✅ Acceptable |
| 69 | 96.55% | `unzipped → unzip` (tense loss) | 🟡 Review |
| 73 | 95.45% | `dingbat → ding-buck` (mispronunciation) | 🔴 Regenerate |

## Quick Reference

### Chunks to Regenerate (Critical Issues)
- **Chunk 52**: `amour → a` (truncation)
- **Chunk 15**: `earbud → air butt` (mispronunciation)
- **Chunk 73**: `dingbat → ding-buck` (mispronunciation)

### Chunks to Investigate (High Priority)
- **Chunk 14**: 0% similarity (formatting issue?)
- **Chunk 58**: 45.88% similarity
- **Chunk 66**: 60.54% similarity
- **Chunk 27, 47, 92, 28, 64, 19, 20, 41**: 70-89% similarity

### Chunks to Review (Medium Priority)
- **Chunk 36**: `condescending → con-sending` (hyphen splitting)
- **Chunk 69**: `unzipped → unzip` (tense loss - may be acceptable)

## Commands to Review

```bash
# Review specific chunk
python scripts/validate_audio.py book_58187 1 --chunk <chunk_index> --full

# Regenerate chunk
curl -X POST "http://localhost:8000/api/chunks/<chunk_index>/generate?book_id=book_58187&chapter_number=1"
```

## Total Summary

- **Critical (<50%)**: 4 chunks
- **High (50-85%)**: 8 chunks  
- **Medium (85-90%)**: 7 chunks
- **Total needing review**: 19 chunks

