#!/usr/bin/env python3
"""Prototype: does regenerate-and-pick (best-of-N) rescue XTTS mangles?

XTTS is stochastic — resynthesizing identical text gives different audio each
time. Prior phoneme-level triage found many real mangles are context-dependent
rolls of the dice rather than words XTTS can never say (chunk 56's "match" is
a clean /matʃ/ in isolation but garbles to "map" in its actual sentence). That
stochasticity is exactly what a regenerate-and-pick gate would exploit: if a
chunk is flagged, throw N fresh takes at it and ship whichever take scores
best, instead of trying to fix the model or the text.

For each (chunk, flagged word) target this script:
  1. Scores the SHIPPED audio's phoneme distance for the word (baseline).
  2. Synthesizes N fresh takes of the same chunk text (new random draws).
  3. Scores each take the same way.
  4. Reports shipped vs. every take vs. best-of-N, and whether best-of-N
     would have avoided an xtts-fault verdict (distance >= XTTS_FAULT_THRESHOLD).

Run in the TTS venv (needs XTTS + the wav2vec2 phoneme model):
  ./venv311/bin/python scripts/prototype_regen_pick.py \
      --target 124774 7 8 56 match \
      --target 124774 7 8 411 Ghanaian \
      --target 124774 7 8 10 Americans \
      --n 3
"""
import argparse
import sys
import tempfile
from dataclasses import dataclass
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


@dataclass
class Target:
    fiction_id: str
    book: int
    chapter: int
    idx: int
    word: str


def _word_distance(chunk_text: str, wav_path: Path, word: str, use_cache: bool) -> float:
    """Phoneme distance of `word`'s pronunciation in `wav_path` vs. its expected
    pronunciation in the context of `chunk_text`. 1.0 if the word can't be
    located in the audio at all (see chunk_word_verdicts)."""
    recognizer = get_phoneme_recognizer()
    phones = recognizer.recognize_wav(wav_path, use_cache=use_cache)
    verdicts = chunk_word_verdicts(chunk_text, phones, targets=[word])
    return verdicts[0]["distance"] if verdicts else 1.0


def _synth_takes(text: str, n: int, tmp_dir: Path) -> list[tuple[Path, float]]:
    """Synthesize n fresh takes of `text`; return (wav_path, gen_seconds) pairs."""
    tts = get_tts_engine()
    takes = []
    for i in range(n):
        out = tmp_dir / f"take_{i}.wav"
        _, elapsed = tts.synthesize(text, out)
        takes.append((out, elapsed))
    return takes


def evaluate_target(target: Target, n: int) -> dict:
    """Score shipped audio + N regeneration takes for one (chunk, word) target."""
    disc = ChunkDiscovery()
    chunk = disc.get_chunk(target.fiction_id, target.book, target.chapter, target.idx)
    if chunk is None or not chunk.has_audio:
        raise SystemExit(f"No chunk/audio for {target}")

    shipped_dist = _word_distance(chunk.text, chunk.audio_path, target.word, use_cache=True)

    with tempfile.TemporaryDirectory(prefix="regen_pick_") as tmp:
        takes = _synth_takes(chunk.text, n, Path(tmp))
        take_scores = [
            (_word_distance(chunk.text, wav, target.word, use_cache=False), elapsed)
            for wav, elapsed in takes
        ]

    best_dist = min(d for d, _ in take_scores)
    return {
        "target": target,
        "shipped_dist": shipped_dist,
        "take_dists": [d for d, _ in take_scores],
        "best_dist": best_dist,
        "total_synth_seconds": sum(t for _, t in take_scores),
        "shipped_was_fault": shipped_dist >= XTTS_FAULT_THRESHOLD,
        "best_is_fault": best_dist >= XTTS_FAULT_THRESHOLD,
    }


def _print_report(result: dict) -> None:
    t = result["target"]
    print(f"\n=== {t.fiction_id} book{t.book} ch{t.chapter} chunk{t.idx:03d} — {t.word!r} ===")
    tag = "[XTTS FAULT]" if result["shipped_was_fault"] else "[ok]"
    print(f"  shipped audio distance : {result['shipped_dist']:.3f}  {tag}")
    for i, d in enumerate(result["take_dists"]):
        tag = "[XTTS FAULT]" if d >= XTTS_FAULT_THRESHOLD else "[ok]"
        print(f"  take {i + 1} distance      : {d:.3f}  {tag}")
    n = len(result["take_dists"])
    tag = "[still fault]" if result["best_is_fault"] else "[CLEAN]"
    print(f"  BEST-OF-{n} distance    : {result['best_dist']:.3f}  {tag}")
    rescued = result["shipped_was_fault"] and not result["best_is_fault"]
    print(f"  best-of-N improved on shipped : {result['best_dist'] < result['shipped_dist']}")
    print(f"  best-of-N RESCUED a fault     : {rescued}")
    print(f"  synth cost                    : {result['total_synth_seconds']:.1f}s for {n} takes")


def _print_summary(results: list[dict]) -> None:
    print("\n=== SUMMARY ===")
    for r in results:
        t = r["target"]
        if not r["shipped_was_fault"]:
            verdict = "N/A (shipped was already clean)"
        elif not r["best_is_fault"]:
            verdict = "RESCUED"
        else:
            verdict = "NOT rescued"
        print(
            f"  chunk{t.idx:03d} {t.word!r}: shipped={r['shipped_dist']:.3f} "
            f"best={r['best_dist']:.3f}  -> {verdict}"
        )


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--target", nargs=5, action="append", metavar=("FICTION", "BOOK", "CH", "IDX", "WORD"),
        required=True, help="Chunk + flagged word to test (repeatable)",
    )
    p.add_argument("--n", type=int, default=3, help="Number of regeneration takes")
    return p.parse_args()


def main():
    args = parse_args()
    targets = [
        Target(fiction_id=f, book=int(b), chapter=int(c), idx=int(i), word=w)
        for f, b, c, i, w in args.target
    ]
    results = []
    for t in targets:
        print(f"\n>>> evaluating {t.fiction_id} book{t.book} ch{t.chapter} "
              f"chunk{t.idx:03d} ({t.word!r}): shipped + {args.n} takes...", flush=True)
        r = evaluate_target(t, args.n)
        _print_report(r)
        results.append(r)
    _print_summary(results)


if __name__ == "__main__":
    main()
