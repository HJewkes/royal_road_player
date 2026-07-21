# TTS issue rates — phoneme-triaged audit

Built by `scripts/build_dataset.py` from the two-phase (base→small Whisper) detector plus a phoneme verdict (espeak G2P vs wav2vec2 phones). Each confirmed defect is labeled **xtts** (genuine mispronunciation — bad audio) or **whisper** (audio correct, Whisper misread).

## Headline

- Chapters audited: **5**  ·  chunks with audio: **2422**
- Confirmed defects (post two-phase): **561**
- Genuine XTTS mispronunciations: **135** (24% of confirmed)
- Whisper misreads of correct audio: **426** (76% of confirmed)
- Bad-audio chunk rate: **5.24%** (127 of 2422 chunks)

> Most flagged "mangles" are Whisper's vocabulary limits, not TTS defects. The genuine-defect rate per chunk is the number that matters for quality.

## Per chapter

| Book | Ch | Chunks | Confirmed | XTTS-fault | Whisper-fault | Bad chunks | Issue rate |
|-----:|---:|-------:|----------:|-----------:|--------------:|-----------:|-----------:|
| 6 | 14 | 492 | 93 | 29 | 64 | 28 | 5.69% |
| 6 | 15 | 520 | 127 | 30 | 97 | 27 | 5.19% |
| 7 | 12 | 477 | 100 | 23 | 77 | 21 | 4.4% |
| 7 | 3 | 438 | 133 | 33 | 100 | 31 | 7.08% |
| 7 | 8 | 495 | 108 | 20 | 88 | 20 | 4.04% |

## Cause breakdown (genuine XTTS faults)

- `(none)`: 67
- `unusual_word`: 51
- `chunk_boundary`: 14
- `stylized_elongation`: 12
- `number`: 1

## Hallucinated outbursts

A separate, arguably more disruptive defect: phantom audio the TTS injects with no matching text (phantom words, babble, drum-vocalisation), found by `scan_hallucinations.py` (phoneme-alignment insertions across every chunk) and tightened by `filter_hallucinations.py` into confidence tiers.

- Raw injected-phoneme findings: **150**
- Confirmed / likely (kept): **123** — a **5.08%** chunk rate (on par with the mispronunciation rate; often more jarring to hear).
- Tiers: confirmed 98, likely 25, borderline 23, probable-FP 4.

Main causes (from the sweep): mid-chunk `."\n\n` paragraph boundaries (fixed — chunker now splits paragraphs), trailing chunk-end fragments/quotes (~half of cases — candidate next fix), and onomatopoeia rendering.

## Test-set files

- `data/test_set/tts_defects.jsonl` — one labeled record per confirmed defect
- `data/test_set/chunk_labels.jsonl` — per-chunk label (bad / flagged_ok)
- `data/test_set/hallucinations.jsonl` — confirmed+likely hallucinated outbursts

Labels are model-derived (phoneme verdict), suitable as a regression baseline for fix experiments — not hand-verified ground truth.

## Known limitation

The phoneme distance is a character-ratio (SequenceMatcher) over IPA strings, which is blind to same-length, same-position diphthong-class swaps (e.g. NAY→NYE in *Ghanaian*). So the XTTS-fault count is a mild **under**-count — some genuine mispronunciations score below the 0.45 threshold and land in *flagged_ok*. A phone-alignment-aware distance would tighten this. Treat the bad-chunk rate as a conservative floor.
