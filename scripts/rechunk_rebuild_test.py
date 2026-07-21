#!/usr/bin/env python3
"""Paired rechunk/rebuild test — does the chunking fix actually kill hallucinations?

XTTS is stochastic: a chunk that babbles hallucinates only ~1/3 of the time, so
regenerating the SAME text sometimes comes out clean by luck. To separate the
*fix* effect from that re-roll luck, every confirmed/likely hallucinating chunk is
synthesized N times in two arms:

  control  — the OLD shipped text, as-is (re-roll baseline)
  fix      — re-chunked with the new TextChunker (paragraph split + trailing-quote
             strip), each resulting sub-chunk synthesized; a rep counts as
             hallucinated if ANY sub-chunk babbles (the delivered audio is the concat)

Reported: per-chunk control vs fix hallucination counts, and the aggregate rate
before/after. When the fix arm comes out clean on a chunk whose control still
babbled, the regenerated audio is saved so the HTML demo can play a real
before(shipped)/after(rebuilt) pair.

Writes incrementally (resumable) to logs/rechunk_test.json.

  ./venv311/bin/python scripts/rechunk_rebuild_test.py            # all confirmed+likely
  ./venv311/bin/python scripts/rechunk_rebuild_test.py --reps 3 --limit 20
"""
import argparse
import json
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.text.chunker import TextChunker  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)

FILTERED = ROOT / "logs" / "hallucinations_filtered.json"
OUT = ROOT / "logs" / "rechunk_test.json"
CLIPS = ROOT / "logs" / "rechunk_clips"


def _synth_halluc(text, tts, recog):
    """Synthesize `text` once; return (wav_path, hallucinations)."""
    wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    tts.synthesize(text, wav)
    halluc = detect_hallucinations(text, recog.recognize(load_slice(wav, None, None)))
    return wav, halluc


def _concat_wavs(paths, out):
    """Concatenate 24k mono XTTS wavs into one file."""
    with wave.open(str(paths[0])) as w0:
        params = w0.getparams()
    with wave.open(str(out), "wb") as wout:
        wout.setparams(params)
        for p in paths:
            with wave.open(str(p)) as w:
                wout.writeframes(w.readframes(w.getnframes()))
    return out


def _run_arm(texts, reps, tts, recog):
    """Synthesize a list of sub-chunk texts `reps` times.

    Returns (hits, worst_severity, first_clean_wavs) where a rep hallucinates if
    ANY sub-chunk does, and first_clean_wavs is the sub-chunk wav list from the
    first fully-clean rep (for the demo), else None.
    """
    hits, worst, clean_wavs = 0, 0.0, None
    for _ in range(reps):
        rep_wavs, rep_halluc = [], []
        for t in texts:
            wav, halluc = _synth_halluc(t, tts, recog)
            rep_wavs.append(wav)
            rep_halluc.extend(halluc)
        if rep_halluc:
            hits += 1
            worst = max(worst, max(h["severity"] for h in rep_halluc))
        elif clean_wavs is None:
            clean_wavs = rep_wavs
    return hits, round(worst, 3), clean_wavs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fresh", action="store_true", help="ignore existing progress")
    args = ap.parse_args()

    rows = [r for r in json.loads(FILTERED.read_text())["rows"]
            if r["tier"] in ("confirmed", "likely")]
    rows.sort(key=lambda r: (r["book"], r["chapter"], r["chunk"]))
    if args.limit:
        rows = rows[:args.limit]

    done = {}
    if OUT.exists() and not args.fresh:
        for r in json.loads(OUT.read_text()).get("results", []):
            done[(r["book"], r["chapter"], r["chunk"])] = r

    CLIPS.mkdir(parents=True, exist_ok=True)
    disc, tts, recog = ChunkDiscovery(), get_tts_engine(), get_phoneme_recognizer()
    chunker = TextChunker()
    results = list(done.values())

    for i, row in enumerate(rows, 1):
        key = (row["book"], row["chapter"], row["chunk"])
        if key in done:
            continue
        chunk = disc.get_chunk("124774", *key)
        if not chunk:
            continue
        old = chunk.text
        new_texts = [c.text for c in chunker.chunk(old)]

        c_hits, c_worst, _ = _run_arm([old], args.reps, tts, recog)
        f_hits, f_worst, clean = _run_arm(new_texts, args.reps, tts, recog)

        after_clip = None
        if clean and c_hits > 0 and f_hits == 0:
            dest = CLIPS / f"b{key[0]}_ch{key[1]}_{key[2]:03d}_after.wav"
            _concat_wavs(clean, dest)
            after_clip = str(dest)

        rec = {
            "book": key[0], "chapter": key[1], "chunk": key[2],
            "tier": row["tier"], "phones": row["phones"], "position": row["position"],
            "old_text": old, "new_texts": new_texts, "n_new": len(new_texts),
            "reps": args.reps,
            "control_hits": c_hits, "control_worst": c_worst,
            "fix_hits": f_hits, "fix_worst": f_worst,
            "fixed": c_hits > 0 and f_hits == 0,
            "shipped_wav": str(chunk.audio_path), "after_wav": after_clip,
        }
        results.append(rec)
        OUT.write_text(json.dumps({"reps": args.reps, "results": results}, indent=2))
        print(f"[{i}/{len(rows)}] b{key[0]}/ch{key[1]}/{key[2]:03d} "
              f"({row['tier']})  control {c_hits}/{args.reps}  fix {f_hits}/{args.reps}"
              f"{'  ->splits '+str(len(new_texts)) if len(new_texts)>1 else ''}"
              f"{'  ✓fixed' if rec['fixed'] else ''}", flush=True)

    _summarize(results, args.reps)


def _summarize(results, reps):
    n = len(results)
    if not n:
        print("no results")
        return
    c_total = sum(r["control_hits"] for r in results)
    f_total = sum(r["fix_hits"] for r in results)
    denom = n * reps
    fixed = sum(1 for r in results if r["fixed"])
    still = sum(1 for r in results if r["fix_hits"] > 0)
    print(f"\n=== rechunk/rebuild — {n} chunks × {reps} reps ===")
    print(f"control (old text) hallucinated reps: {c_total}/{denom} "
          f"({100*c_total/denom:.1f}%)")
    print(f"fix (rechunked)    hallucinated reps: {f_total}/{denom} "
          f"({100*f_total/denom:.1f}%)")
    print(f"reduction in hallucinated reps: {100*(c_total-f_total)/c_total:.0f}%"
          if c_total else "n/a")
    print(f"chunks fully fixed (control babbled, fix clean all reps): {fixed}/{n}")
    print(f"chunks still hallucinating at least once under fix: {still}/{n}")


if __name__ == "__main__":
    main()
