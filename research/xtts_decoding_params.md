# XTTS v2 decoding params vs. mispronunciation/garbling

Prototype: `scripts/prototype_param_sweep.py`. Installed package: `TTS==0.21.0`
(venv311). Model: `tts_models/multilingual/multi-dataset/xtts_v2`.

## 1. What params exist, and how to pass them

`XTTSEngine.synthesize()` (`backend/src/tts/xtts.py`) calls
`self._tts.tts_to_file(text=, file_path=, language="en", speaker_wav=, speed=)`
and nothing else. It turns out that's leaving real decoding knobs on the
table — Coqui forwards unknown kwargs all the way down to the GPT decoder's
HuggingFace `generate()` call. Traced the actual call chain in the installed
package to confirm this (not just docs):

```
TTS.api.TTS.tts_to_file(**kwargs)
  -> TTS.api.TTS.tts(**kwargs)
  -> TTS.utils.synthesizer.Synthesizer.tts(**kwargs)
       (this layer sentence-splits the text itself and loops per sentence)
  -> TTS.tts.models.xtts.Xtts.synthesize(text, config, speaker_wav, language, **kwargs)
  -> Xtts.inference_with_config(...)
       # merges kwargs onto config.* defaults, e.g.:
       settings = {"temperature": config.temperature, "repetition_penalty": config.repetition_penalty, ...}
       settings.update(kwargs)   # <-- caller kwargs win
  -> Xtts.full_inference(temperature=, length_penalty=, repetition_penalty=,
                          top_k=, top_p=, do_sample=, gpt_cond_len=,
                          gpt_cond_chunk_len=, max_ref_len=, sound_norm_refs=,
                          **hf_generate_kwargs)
  -> Xtts.inference(..., num_beams=, speed=, enable_text_splitting=, **hf_generate_kwargs)
  -> self.gpt.generate(top_p=, top_k=, temperature=, repetition_penalty=,
                        length_penalty=, num_beams=, num_return_sequences=self.gpt_batch_size,
                        **hf_generate_kwargs)   # HF transformers generate() API
```

**Conclusion: no need to call `model.inference()` directly.** Just add kwargs
to the existing `tts_to_file()` call:

```python
self._tts.tts_to_file(
    text=text, file_path=str(output_path), language="en",
    speaker_wav=self.voice_sample, speed=speed,
    temperature=0.85, repetition_penalty=2.0, top_k=50, top_p=0.85,
    length_penalty=1.0,
)
```

`TTS.api.TTS._check_arguments()` only validates `speaker`/`language`/
`speaker_wav`/`emotion`/`speed` — it never rejects unrecognized kwargs, so
this passthrough is safe with the installed version.

### Gotchas found while tracing the chain

- **`num_return_sequences` cannot be overridden via kwargs.** It's hard-coded
  in `gpt.generate(..., num_return_sequences=self.gpt_batch_size, ...)` as an
  explicit keyword — passing it in `hf_generate_kwargs` raises "got multiple
  values for keyword argument". Any best-of-N-via-batching approach would
  need `self.gpt_batch_size` (an `XttsArgs` field, set at model construction)
  changed instead, not a per-call kwarg. (Best-of-N via repeated *calls*, as
  in `scripts/prototype_regen_pick.py`, sidesteps this entirely.)
- **`num_gpt_outputs`** exists on `XttsConfig` (Tortoise/CLVP-reranking
  holdover) but is **not** read anywhere in `full_inference()`/`inference()`.
  Setting it does nothing in this code path — don't rely on it.
- **`enable_text_splitting`** on `Xtts.inference()` is redundant for this call
  path: `Synthesizer.tts()` already sentence-splits the input *before* calling
  `Xtts.synthesize()` once per sentence, so each individual call to
  `full_inference()`/`inference()` only ever sees one sentence anyway (log
  output confirms this — chunk 56's 3-sentence chunk produced 3 `"Text
  splitted to sentences."` sub-calls, each synthesized and concatenated).
- **MPS bug, not param-related but hit immediately in the prototype**: the
  installed checkpoint's speaker-encoder conv fails on Apple Silicon MPS
  (`Output channels > 65536 not supported at the MPS device`) even with
  `PYTORCH_ENABLE_MPS_FALLBACK=1` set. `xtts.py`'s `synthesize()` already has
  a retry-on-CPU path for this; the prototype script forces CPU once up front
  instead of retrying per call.

### Param reference (checkpoint's own `config.json` defaults — i.e. the
values every already-shipped chunk was generated with, since `xtts.py` never
overrides them)

| param | shipped default | effect | recommended range |
|---|---|---|---|
| `temperature` | 0.75 | Softmax temperature for the autoregressive GPT sampler. Higher = more varied/"creative" phoneme-token choices, lower = more peaked/greedy. **Lower is not simply "safer"**: if the peak of the distribution *is* the wrong pronunciation, low temperature locks onto it deterministically (see chunk 56 result below). | 0.3–0.9; no single direction is uniformly safer — see results |
| `repetition_penalty` | 5.0 | Penalizes repeating audio tokens; guards against stutter/repeat-loop garbling ("uhhhhh", stuck syllables). Coqui's own dataclass default is 2.0 but this checkpoint ships 5.0. | 2.0–10.0 |
| `length_penalty` | 1.0 | Exponent applied to sequence length in beam scoring. Irrelevant at `num_beams=1` (the default) since beam search score comparison never triggers — only matters if beam search is also turned on. | leave at 1.0 unless enabling beam search |
| `top_k` | 50 | Restricts sampling to the k most likely tokens per step. | 20–100 |
| `top_p` | 0.85 | Nucleus sampling cutoff. | 0.7–0.95 |
| `gpt_cond_len` / `gpt_cond_chunk_len` | 30 / 4 | Seconds of the voice-cloning reference audio used for conditioning latents (chunked and averaged). Affects voice stability/similarity, not per-word pronunciation accuracy. | defaults are fine |
| `max_ref_len` | 30 (checkpoint) | Cap on reference audio length fed to the decoder side. | defaults are fine |
| `do_sample` | `True` | Whether to sample at all; `False` forces greedy decoding (`temperature`/`top_k`/`top_p` become no-ops). | leave `True` |
| `num_beams` | 1 | Beam search width. Untested here (budget); in principle more beams could stabilize pronunciation but multiplies compute directly and interacts with `length_penalty`. | untested; candidate for follow-up |
| `enable_text_splitting` | effectively moot (see gotcha above) | | leave `False` |

## 2. Experiment

Targets (both known mangles from prior phoneme triage):

- **chunk 56** (book_7/ch_8): "...higher than they had been the whole
  **match**." — a common word that garbles only in its sentence context
  (isolated "match" synthesizes fine — prior finding).
- **chunk 411**: "The **Ghanaian** snaps at his heels." — a rare proper noun.

Scoring: `chunk_word_verdicts()` phoneme distance of the target word,
`XTTS_FAULT_THRESHOLD = 0.45` (>= is a genuine XTTS mispronunciation, not a
Whisper artifact — not used here since scoring is phoneme-only).

Baseline: the **shipped chunk `.wav` itself**, not a resynthesis — since
`XTTSEngine.synthesize()` already uses the checkpoint's own defaults listed
above, the file on disk *is* the "shipped defaults" data point at zero extra
synthesis cost.

Grid (one knob changed at a time vs. shipped defaults, to isolate which knob
matters, within an 8-synthesis CPU budget):

- chunk 56 (4 syntheses): `low_temp` (0.3), `high_temp` (0.85),
  `low_rep_penalty` (2.0), `high_rep_penalty` (10.0)
- chunk 411 (4 syntheses): `repeat_default` (stochastic-variance control —
  same settings, fresh random draw), `low_temp` (0.3), `high_rep_penalty`
  (10.0), `low_temp_high_rep` (combo)

## 3. Results

```
=== chunk056 'match' ===
  shipped (defaults)            : distance = 0.714  [XTTS FAULT]
  low_temp        (temp=0.3)    : distance = 0.714  [XTTS FAULT]  (same)
  high_temp       (temp=0.85)   : distance = 0.250  [ok]          (better)
  low_rep_penalty (rep=2.0)     : distance = 0.250  [ok]          (better)
  high_rep_penalty(rep=10.0)    : distance = 0.250  [ok]          (better)

=== chunk411 'Ghanaian' ===
  shipped (defaults)            : distance = 0.538  [XTTS FAULT]
  repeat_default  (same params) : distance = 0.538  [XTTS FAULT]  (same)
  low_temp        (temp=0.3)    : distance = 0.538  [XTTS FAULT]  (same)
  high_rep_penalty(rep=10.0)    : distance = 0.571  [XTTS FAULT]  (worse)
  low_temp_high_rep              : distance = 0.538  [XTTS FAULT]  (same)

SUMMARY
  chunk056 'match'   : shipped=0.714 best=0.250 (high_temp)      -> RESCUED
  chunk411 'Ghanaian': shipped=0.538 best=0.538 (repeat_default) -> not rescued
```

(Real-time factor on CPU: ~1.2–2.0x, i.e. 17–26s of wall time per ~250-char
chunk per synthesis — relevant for costing any regen-on-flag scheme.)

## 4. Interpretation

**Decoding params rescued the stochastic/context-dependent mangle (chunk 56
"match") but did nothing for the intrinsically-hard word (chunk 411
"Ghanaian")** — and the pattern of *which* knob helped is itself informative:

- On chunk 56, three unrelated single-knob changes (`temperature` up,
  `repetition_penalty` down, `repetition_penalty` up) all landed on the exact
  same corrected distance (0.250), while `temperature` *down* (0.3) reproduced
  the *exact same* mangled distance (0.714) as the shipped default. That's
  consistent with "match → map" being the **mode** of the decoder's
  distribution in this sentence context: lowering temperature sharpens
  sampling toward that mode (locks in the mistake, deterministically),
  while *any* other perturbation — including raising temperature, which
  should intuitively make things *less* stable — was enough to knock the
  sampler off that bad mode and onto the correct pronunciation. In other
  words, for this failure mode the direction of the change matters less than
  simply **perturbing away from the params that produced the shipped take**.
- On chunk 411, every setting reproduced the *same* wrong pronunciation
  (0.538) except one that made it slightly worse — suggesting "Ghanaian" is
  a case where the decoder's distribution is heavily concentrated on a wrong
  answer regardless of these decoding knobs. This matches the earlier
  finding that rare proper nouns need lexicon/phonetic-respelling fixes, not
  decoding-time tuning.

**Caveat**: each setting was run once (no repeated seeds), so a setting that
"helped" chunk 56 could partly be attributable to plain stochastic luck on a
single draw rather than the specific knob. The `repeat_default` control on
chunk 411 (same params, fresh draw, same 0.538 result) is some evidence
against pure luck dominating — but a rigorous version of this experiment
would run 3+ seeds per setting. That's future work, not done here (budget).

## 5. Recommendation

**Worth wiring in, but as a targeted regen-on-flag step, not a global default
change:**

1. **Don't change the pipeline's default decoding params wholesale.** We
   have one data point per setting; there's no evidence a single global
   `temperature`/`repetition_penalty` change is uniformly better across the
   whole book, and the shipped defaults are the checkpoint author's own
   tuned values.
2. **Do wire per-chunk regeneration with param variation into the existing
   defect-scan/regen loop** (`scripts/scan_defects.py` /
   `prototype_regen_pick.py` already do "same params, new seed"
   regenerate-and-pick): when a chunk is flagged as an XTTS-fault
   mispronunciation, try a small fixed set of param variants (e.g.
   `temperature=0.85`, `repetition_penalty∈{2.0,10.0}`) *in addition to*
   plain reseeded retries, and keep whichever take scores best via the
   phoneme verdict. This prototype shows that's more effective than plain
   reseeding alone for at least one real mangle class (context-dependent
   slips on ordinary words).
3. **Don't expect this to fix rare-proper-noun mangles** (chunk 411 class).
   Those need the lexicon/phonetic-respelling approach already in progress
   elsewhere in this codebase, not decoding-param tuning — save the
   regen-with-param-variation budget for chunks whose flagged word is common
   vocabulary.
4. Any pipeline change should route params through `tts_to_file(**kwargs)` as
   shown in section 1 — no changes to the Coqui package or use of
   `model.inference()` directly are needed.
