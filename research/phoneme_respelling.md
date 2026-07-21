# Phoneme-grounded respelling: prototype results

Prototype code: `scripts/prototype_phoneme_respell.py` (standalone; does not touch
`src/text/lexicon.py`). Run with `./venv311/bin/python scripts/prototype_phoneme_respell.py`.

Question: can we generate lexicon-respelling candidates *from a word's target
IPA* (phoneme-grounded) instead of the current ad-hoc grapheme-mutation rules
in `generate_candidates()`, and can a cheap "isolation filter" reliably tell us
*which* mispronunciations a respelling could even fix?

**Bottom line up front:** the isolation filter behaved correctly on the one
case where we already had reliable ground truth ("match"), and it flagged our
other test case ("Ghanaian") as *not* cleanly intrinsic either — contradicting
the assumption in the task brief that it was a safe intrinsic target. The
candidate sweep on "Ghanaian" found no winner and one regression, which is
exactly what the filter's verdict would predict. That's a successful
demonstration of the filter's value (it would have stopped a wasted/harmful
lexicon edit) but it means we don't yet have a clean positive case proving
phoneme-grounded respelling *fixes* a real intrinsic mangle end-to-end. See
"Honest recommendation" at the end.

## 1. IPA → grapheme table

espeak-ng's `--ipa=3` output (via `g2p()` in `src/validation/phonemes.py`,
which already strips stress/length marks) is segmented into phones by greedy
longest-match (2-char phones like `tʃ`, `eɪ`, `əʊ` first, then single
characters), and each phone maps to a primary grapheme XTTS is expected to
render reliably, plus alternates used to generate single-substitution
variants.

| Phone | Primary | Alternates | Example |
|---|---|---|---|
| i | ee | i | see |
| ɪ | i | ih | sit |
| ɛ | eh | e | set |
| e | eh | ay | (rare standalone) |
| æ | a | ae | cat |
| a | ah | a | (foreign/short open front — Ghanaian) |
| ɑ | ah | aa | father |
| ɒ | o | ah | hot |
| ɔ | aw | or | saw |
| ʊ | oo | u | put |
| u | oo | u | food |
| ʌ | uh | u | cup |
| ɜ | ur | er | bird |
| ə | uh | a, e | schwa |
| ɐ | uh | a | about (1st syllable) |
| eɪ | ay | ai | say |
| aɪ | y | eye, igh | sky |
| ɔɪ | oy | oi | boy |
| əʊ | oh | o | go |
| aʊ | ow | ou | cow |
| ɪə | eer | ear | beer |
| eə | air | are | bear |
| ʊə | oor | ure | tour |
| p b t d k ɡ f v s z h m n l w | (identity) | — | — |
| ŋ | ng | — | sing |
| ɹ | r | — | red |
| j | y | — | yes |
| ʃ | sh | — | she |
| ʒ | zh | si | measure |
| θ | th | — | thin |
| ð | th | — | this (**same grapheme as θ — see caveats**) |
| tʃ | ch | tch | church |
| dʒ | j | dge, g | judge |
| x | ch | k | loch (foreign names) |

Candidate generation (`generate_phoneme_respellings`):
1. Baseline candidate = all primary graphemes concatenated.
2. One variant per phone that has an alternate grapheme (single point of
   difference from baseline — keeps each candidate explainable: "phone N was
   respelled X instead of Y").
3. A generalizable ending-specific rule: word-final unstressed `ə+n` ("-ən")
   is a common English orthographic ending spelled "-an"/"-en"/"-on" (African,
   garden, wagon) rather than literally "-uhn" — adds those 3 variants when
   applicable. This is a rule about English orthography, not about the word
   "Ghanaian" specifically.

## 2. Isolation filter design

`isolation_verdict(word, tts, recognizer)` synthesizes the bare word inside a
neutral carrier (`"I travelled to {} last year."`), transcribes the audio with
the vocab-free wav2vec2 phoneme recognizer, and reuses
`chunk_word_verdicts()` (already built for exactly this: locate a word's
G2P inside a chunk's G2P, read the positionally-aligned actual-audio span,
verdict via `phoneme_distance` and the existing `XTTS_FAULT_THRESHOLD=0.45`).

Classification:
- `source == 'xtts'` (distance ≥ 0.45) in isolation → **intrinsic**: the word
  itself is broken; a respelling is a legitimate candidate fix.
- `source == 'whisper'` (distance < 0.45) in isolation but `xtts` in the
  original chunk context → **contextual**: the word is fine alone; a lexicon
  respelling cannot help (and risks regressing the clean, isolated case).

`context_verdict()` reuses **already-generated** chunk audio on disk (no new
XTTS synthesis) to get the in-context verdict for free — the pipeline had
already rendered chunk 411 (ch8, "Ghanaian") and chunk 56 (ch8, "match").

## 3. Measured results

### Step 0 — old vs new candidate generation (no synthesis)

Target: "Ghanaian", espeak IPA `ɡaneɪən` ("Gha-NAY-an").

- Old `generate_candidates("Ghanaian")` → **`[]`**. Its rule set (wr-/kn-
  prefixes, `ph`, `ough`/`augh`, `x`, `y`, `ch`, silent trailing `e`, `-ham`,
  double-consonants) has zero coverage for this word's actual failure mode —
  a foreign-name vowel/diphthong substitution — so it doesn't even attempt a
  fix.
- New `generate_phoneme_respellings("Ghanaian")` →
  `['Gahnayuhn', 'Ganayuhn', 'Gahnaiuhn', 'Gahnayan', 'Gahnayen', 'Gahnayon']`
  — every candidate directly targets the `eɪ`/`ə` phones from the *actual*
  target pronunciation.

This is a real, structural advantage: the ad-hoc generator has a rule-shaped
blind spot for exactly the class of error (foreign proper-noun vowel swaps)
this whole project cares about; the phoneme-grounded generator always
produces *something* traceable to the target phones.

### Step 1 — in-context evidence (reused audio, zero new synthesis)

| Word | In-context distance | Verdict | Expected | Actual |
|---|---|---|---|---|
| Ghanaian (ch8 chunk 411) | 0.538 | `xtts` (real mangle) | `ɡaneɪən` | `ɡənaɪn` |
| match (ch8 chunk 56) | 0.714 | `xtts` (real mangle) | `matʃ` | `mæk` |

Both score as genuine XTTS faults in their original sentence context.

### Step 2 — isolation filter (1 new synthesis each)

| Word | Isolation distance | Verdict | Expected | Actual |
|---|---|---|---|---|
| Ghanaian | 0.286 | **clean-in-isolation** | `ɡaneɪən` | `ɡənaɪən` |
| match | 0.250 | **clean-in-isolation** | `matʃ` | `mætʃ` |

`match` isolating clean matches the known ground truth from prior manual
investigation (this is the case the task brief cites as the canonical
contextual example) — good validation that the filter mechanism works.

`Ghanaian` *also* isolates clean (0.286 < 0.45 threshold) — this is the
surprising result. The task brief characterized Ghanaian as an intrinsic
mangle ("Gha-NINE vs Gha-NAY-an"), but this measurement disagrees: by the
filter's own rule, Ghanaian is contextual too, not a safe respelling target.

**Important caveat on that verdict.** Look at the actual isolation audio:
`ɡənaɪən` vs expected `ɡaneɪən`. That *is* the NAY→NYE diphthong swap
(`eɪ`→`aɪ`) the task brief describes as the known defect — it's sitting right
there in the phones. But `phoneme_distance` is a character-level
`SequenceMatcher` ratio over the IPA string, and the phones before/after the
swapped diphthong (`ɡ, n, ə, n`) still line up, so the ratio stays high enough
(0.286) to read as "clean." **The metric under-detects a same-position,
same-length diphthong-class substitution because it isn't phone-boundary
aware.** This is a real gap: a binary 0.45 threshold built on a
lenient string-similarity metric will sometimes call an audibly-wrong vowel
"fine." Combined with XTTS's run-to-run stochasticity (this is a single
sample per word — no repeat-averaging, per the synthesis budget), the
isolation-vs-context gap here is likely a mix of genuine context sensitivity
*and* both measurement noise and metric insensitivity, and this prototype
cannot fully separate the three with n=1.

We also checked (for free, reusing already-generated chunk audio, no new
synthesis) the other known ch8 mangle candidates from `scripts/phoneme_check.py`
— Wythenshawe, boshtastic, enormo, Wrexham, Kisi — none scored as an
in-context XTTS fault under this phoneme method (all below 0.45), so none of
them offered a cleaner intrinsic test case within today's synthesis budget.

### Step 3 — candidate sweep for "Ghanaian" (4 new syntheses)

Scored against the *original* word's expected phones, positionally located
via `chunk_word_verdicts` (same machinery as the in-context checks).

| Spelling | Distance | Verdict | Actual phones |
|---|---|---|---|
| Ganayuhn | 0.286 | whisper (tie w/ baseline) | `ɡanəjun` |
| Gahnaiuhn | 0.286 | whisper (tie w/ baseline) | `ɡənaɪən` |
| Gahnayan | 0.286 | whisper (tie w/ baseline) | `ɡənaɪən` |
| Gahnayuhn | 0.500 | **xtts (regression)** | `ɡɑnəj` |
| *baseline* "Ghanaian" | 0.286 | whisper | `ɡənaɪən` |

**No candidate beat the orthographic baseline.** Three tied it exactly; one
("Gahnayuhn" — the primary/all-defaults candidate) scored *worse* and crossed
into fault territory, dropping the final `n` entirely. This is consistent with
the isolation filter's verdict: since "Ghanaian" wasn't a clean intrinsic
case, there was no real defect for a respelling to fix, and one respelling
attempt actively made things worse.

## 4. Honest recommendation

1. **Keep the isolation filter as a mandatory gate before any lexicon write.**
   It's cheap (one extra synthesis per candidate word) and in this run it
   would have stopped exactly the kind of wasted/harmful edit we saw in the
   sweep (a candidate that regressed a word that was already fine alone).
   Ship it as a precondition on `sweep_respelling.py --apply`, not just this
   prototype.
2. **Don't trust a single-sample isolation verdict near the threshold.**
   Average 3+ repeats (the existing `sweep_respelling.py` pattern already
   does this for its STT-based scoring) before classifying intrinsic vs
   contextual — XTTS's stochasticity and the character-level distance metric
   both add enough noise to flip a borderline verdict.
3. **The phoneme-distance metric needs a phone-alignment-aware upgrade**
   before it can be trusted on vowel/diphthong-class errors. A
   `SequenceMatcher` character ratio can call `ɡənaɪən` vs `ɡaneɪən` "clean"
   even though the stressed vowel is categorically wrong (NAY vs NYE) — that's
   a metric blind spot, not proof the audio is correct. Consider phone-level
   (not character-level) edit distance with position weighting toward stressed
   syllables, or a minimum per-phone match requirement at the diphthong.
4. **Adopt the phoneme-grounded generator as the candidate source going
   forward — it strictly increases coverage** (it produced a plausible,
   explainable candidate set for a word the current rule-based generator
   couldn't touch at all) even though this run's one sweep didn't find a
   winner. Keep the rule-based generator too since it's cheap and
   complementary (catches English-orthography-irregularity classes the IPA
   table doesn't target, like silent letters).
5. **This prototype does not yet have a validated positive case** — a word
   that (a) reproducibly measures as intrinsic across repeats and (b) is
   demonstrably fixed by a phoneme-grounded candidate. Before generalizing
   this into the pipeline, spend a next round finding one (ideally a foreign
   proper noun with a large vowel-class error, similar in shape to what
   Ghanaian was believed to be) and re-run the same protocol with repeat
   averaging and the improved distance metric from point 3.

## Caveats carried over from the task brief

- `θ`/`ð` share one grapheme (`th`) in this table — English orthography
  doesn't distinguish voiced/voiceless "th" either, so this is an inherent,
  unresolvable ambiguity for grapheme-based respelling, not a bug in the
  table.
- Foreign/loan names are a trap for the *expected* side too: espeak's
  anglicized G2P reference can itself be wrong (the brief's "Bochum" example:
  XTTS's `/bɑkəm/` is arguably closer to the real German than espeak's
  `/bɒtʃəm/`). A low phoneme-distance score against espeak G2P is necessary
  but not sufficient evidence of a correct fix for loanwords — always
  sanity-check against the real target pronunciation, not just espeak's.
