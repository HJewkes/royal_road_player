#!/usr/bin/env python3
"""Prototype: do XTTS v2 DECODING params reduce mispronunciation/garbling?

Prior phoneme-level triage found many real mangles are STOCHASTIC / CONTEXT-
DEPENDENT rather than word-intrinsic: e.g. chunk 56's "match" synthesizes as a
clean /matʃ/ in isolation but garbles (audibly toward "map") in its actual
sentence, and chunk 411's "Ghanaian" mangles too. `prototype_regen_pick.py`
showed regenerate-and-pick-best-of-N (same decoding settings, new random draw)
can rescue these. This script asks a narrower question: instead of (or in
addition to) resampling blind, can we bias generation toward stability by
changing the GPT decoder's own decoding knobs?

Where the knobs come from
--------------------------
`TTS.api.TTS.tts_to_file(**kwargs)` forwards unknown kwargs all the way down:

    tts_to_file(**kwargs)
      -> TTS.tts(**kwargs)
      -> Synthesizer.tts(**kwargs)
      -> Xtts.synthesize(text, config, speaker_wav, language, **kwargs)
      -> Xtts.inference_with_config(...)   # merges kwargs onto config.* defaults
      -> Xtts.full_inference(temperature=, length_penalty=, repetition_penalty=,
                              top_k=, top_p=, do_sample=, gpt_cond_len=,
                              gpt_cond_chunk_len=, max_ref_len=, ...)
      -> Xtts.inference(..., enable_text_splitting=, num_beams=, **hf_generate_kwargs)
      -> self.gpt.generate(top_p=, top_k=, temperature=, repetition_penalty=,
                            length_penalty=, num_beams=, ...)  # HF generate() API

So `tts.tts_to_file(text=..., ..., temperature=0.3, repetition_penalty=10.0)`
just works — no need to call `model.inference()` directly. Verified against
the installed TTS==0.21.0 package
(venv311/lib/python3.11/site-packages/TTS/tts/models/xtts.py); see
research/xtts_decoding_params.md for the full parameter reference.

Baseline == shipped audio
--------------------------
`XTTSEngine.synthesize()` (backend/src/tts/xtts.py) never passes any of these
kwargs, so every chunk already on disk was generated with the XTTS v2
checkpoint's *own* config.json defaults:

    temperature=0.75  length_penalty=1.0  repetition_penalty=5.0
    top_k=50          top_p=0.85          gpt_cond_len=30 gpt_cond_chunk_len=4

That means the already-synthesized chunk .wav is a valid, zero-cost baseline
for this sweep — no need to resynthesize the default settings to get a
baseline score, only to test *changed* settings and (for one target) a
repeat-default control to gauge run-to-run stochastic variance.

Budget: CPU is shared with a concurrent audit job, so this script is designed
for <=8 total XTTS syntheses (a small per-knob grid on chunk 56, plus a
smaller confirmation grid on chunk 411 using the most promising direction).

Run in the TTS venv:
  cd backend && ../venv311/bin/python ../scripts/prototype_param_sweep.py
"""
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    XTTS_FAULT_THRESHOLD,
    chunk_word_verdicts,
    get_phoneme_recognizer,
)

# The XTTS v2 checkpoint's own config.json defaults (data/... /tts_models--
# multilingual--multi-dataset--xtts_v2/config.json) == what every shipped
# chunk was already generated with, since xtts.py never overrides them.
SHIPPED_DEFAULTS = dict(
    temperature=0.75,
    length_penalty=1.0,
    repetition_penalty=5.0,
    top_k=50,
    top_p=0.85,
)


@dataclass
class ParamSetting:
    name: str
    overrides: dict = field(default_factory=dict)

    def kwargs(self) -> dict:
        merged = dict(SHIPPED_DEFAULTS)
        merged.update(self.overrides)
        return merged


@dataclass
class Target:
    fiction_id: str
    book: int
    chapter: int
    idx: int
    word: str
    settings: list  # list[ParamSetting] to try for this target


# --- Chunk 56: "...higher than they had been the whole match." ---
# One knob changed at a time, everything else pinned to shipped defaults.
CHUNK_56_SETTINGS = [
    ParamSetting("low_temp", {"temperature": 0.3}),
    ParamSetting("high_temp", {"temperature": 0.85}),
    ParamSetting("low_rep_penalty", {"repetition_penalty": 2.0}),
    ParamSetting("high_rep_penalty", {"repetition_penalty": 10.0}),
]

# --- Chunk 411: "The Ghanaian snaps at his heels." ---
# Confirmation grid: the two individually-plausible directions, their combo,
# and a repeat-of-defaults control (measures plain stochastic variance so we
# don't mistake "got lucky on resample" for "the param helped").
CHUNK_411_SETTINGS = [
    ParamSetting("repeat_default", {}),
    ParamSetting("low_temp", {"temperature": 0.3}),
    ParamSetting("high_rep_penalty", {"repetition_penalty": 10.0}),
    ParamSetting("low_temp_high_rep", {"temperature": 0.3, "repetition_penalty": 10.0}),
]

TARGETS = [
    Target("124774", 7, 8, 56, "match", CHUNK_56_SETTINGS),
    Target("124774", 7, 8, 411, "Ghanaian", CHUNK_411_SETTINGS),
]


def synthesize_with_params(text: str, out_path: Path, **decoding_kwargs) -> float:
    """Synthesize `text`, forwarding decoding kwargs straight through Coqui's
    kwargs passthrough (tts_to_file -> ... -> Xtts.inference()). Mirrors the
    pre/post-processing in XTTSEngine.synthesize() (backend/src/tts/xtts.py)
    without editing that file: same text preprocessing, same trailing-silence
    padding, same voice sample and language.
    """
    engine = get_tts_engine()
    if not engine.is_loaded:
        engine.load_model()
    # Force CPU: this checkpoint's speaker-encoder conv hits "Output channels >
    # 65536 not supported at the MPS device" on Apple Silicon regardless of
    # PYTORCH_ENABLE_MPS_FALLBACK (xtts.py's synthesize() has a retry-on-CPU
    # path for exactly this; we short-circuit to CPU once instead of retrying
    # per call).
    if engine._device != "cpu":
        engine._tts.to("cpu")
        engine._device = "cpu"
    text = engine._preprocess_text(text)

    t0 = time.time()
    engine._tts.tts_to_file(
        text=text,
        file_path=str(out_path),
        language="en",
        speaker_wav=engine.voice_sample,
        speed=1.0,
        **decoding_kwargs,
    )
    elapsed = time.time() - t0
    engine._add_trailing_silence(out_path)
    return elapsed


def word_distance(chunk_text: str, wav_path: Path, word: str, use_cache: bool) -> float:
    """Phoneme distance of `word` in `wav_path`'s audio vs. its expected
    pronunciation in the context of `chunk_text`. 1.0 if not locatable."""
    recognizer = get_phoneme_recognizer()
    phones = recognizer.recognize_wav(wav_path, use_cache=use_cache)
    verdicts = chunk_word_verdicts(chunk_text, phones, targets=[word])
    return verdicts[0]["distance"] if verdicts else 1.0


def evaluate_target(target: Target, tmp_dir: Path) -> dict:
    disc = ChunkDiscovery()
    chunk = disc.get_chunk(target.fiction_id, target.book, target.chapter, target.idx)
    if chunk is None or not chunk.has_audio:
        raise SystemExit(f"No chunk/audio for {target}")

    shipped_dist = word_distance(chunk.text, chunk.audio_path, target.word, use_cache=True)

    runs = []
    for setting in target.settings:
        out = tmp_dir / f"chunk{target.idx:03d}_{setting.name}.wav"
        kwargs = setting.kwargs()
        elapsed = synthesize_with_params(chunk.text, out, **kwargs)
        dist = word_distance(chunk.text, out, target.word, use_cache=False)
        runs.append({
            "name": setting.name,
            "kwargs": kwargs,
            "wav_path": out,
            "distance": dist,
            "elapsed": elapsed,
        })

    return {"target": target, "shipped_dist": shipped_dist, "runs": runs}


def _fault_tag(dist: float) -> str:
    return "[XTTS FAULT]" if dist >= XTTS_FAULT_THRESHOLD else "[ok]"


def print_report(result: dict) -> None:
    t = result["target"]
    print(f"\n=== {t.fiction_id} book{t.book} ch{t.chapter} chunk{t.idx:03d} — {t.word!r} ===")
    print(f"  shipped (defaults {SHIPPED_DEFAULTS}):")
    print(f"    distance = {result['shipped_dist']:.3f}  {_fault_tag(result['shipped_dist'])}")
    for run in result["runs"]:
        changed = {k: v for k, v in run["kwargs"].items() if SHIPPED_DEFAULTS.get(k) != v}
        changed_str = changed or "(none — repeat of defaults)"
        delta = run["distance"] - result["shipped_dist"]
        arrow = "better" if delta < 0 else ("worse" if delta > 0 else "same")
        print(
            f"  {run['name']:<20} {changed_str}\n"
            f"    distance = {run['distance']:.3f}  {_fault_tag(run['distance'])}"
            f"   (delta {delta:+.3f} vs shipped, {arrow})  [{run['elapsed']:.1f}s]"
        )


def print_summary(results: list) -> None:
    print("\n=== SUMMARY ===")
    for r in results:
        t = r["target"]
        best_run = min(r["runs"], key=lambda x: x["distance"])
        shipped = r["shipped_dist"]
        verdict = (
            "N/A (shipped already clean)" if shipped < XTTS_FAULT_THRESHOLD
            else "RESCUED by params" if best_run["distance"] < XTTS_FAULT_THRESHOLD
            else "not rescued"
        )
        print(
            f"  chunk{t.idx:03d} {t.word!r}: shipped={shipped:.3f} "
            f"best={best_run['distance']:.3f} ({best_run['name']}) -> {verdict}"
        )


def main():
    import tempfile
    results = []
    with tempfile.TemporaryDirectory(prefix="xtts_param_sweep_") as tmp:
        tmp_dir = Path(tmp)
        for target in TARGETS:
            n = len(target.settings)
            print(
                f"\n>>> evaluating {target.fiction_id} book{target.book} "
                f"ch{target.chapter} chunk{target.idx:03d} ({target.word!r}): "
                f"shipped + {n} param settings...",
                flush=True,
            )
            r = evaluate_target(target, tmp_dir)
            print_report(r)
            results.append(r)
        print_summary(results)
        # tmp_dir (and its wavs) are cleaned up on exit; findings are captured
        # from the printed report, not the audio itself.


if __name__ == "__main__":
    main()
