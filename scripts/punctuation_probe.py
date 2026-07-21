#!/usr/bin/env python3
"""Isolate which chunk-ENDINGS trigger XTTS's end-of-utterance babble.

Two controlled series, each a fixed base sentence synthesized N times per variant,
measuring how often a phantom outburst appears and how often it lands at the END
(position > 0.7):

  A. Same words, different terminal punctuation  (. vs ." vs bare " vs none vs ! ? … ,)
  B. Same trailing punctuation (.), different final-WORD type (common / proper noun / number)

This tests the hypothesis that the babble is an end-of-utterance effect driven by
weak terminal cues (silent trailing quote, a period after a name/number), not by
punctuation in general.

  ./venv311/bin/python scripts/punctuation_probe.py [--reps 10]
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)

OUT = ROOT / "logs" / "punctuation_probe.json"

BASE_A = "He nodded slowly and told the whole team to keep their heads up"
SERIES_A = [
    ("plain period  .",        BASE_A + "."),
    ("quoted        .\"",      '"' + BASE_A + '."'),
    ("bare quote    \"",       BASE_A + '"'),
    ("no punctuation",         BASE_A),
    ("exclaim       !",        BASE_A + "!"),
    ("question      ?",        BASE_A + "?"),
    ("ellipsis      …",        BASE_A + "…"),
    ("comma         ,",        BASE_A + ","),
]
SERIES_B = [
    ("ends common word .",     "He nodded slowly and rolled the ball out to the winger."),
    ("ends proper noun .",     "He nodded slowly and rolled the ball out to Bamba."),
    ("ends bare number .",     "He nodded slowly and they moved the score along to 16."),
]


def _rate(text, tts, recog, reps):
    any_hits = end_hits = 0
    worst = 0.0
    for _ in range(reps):
        wav = Path(tempfile.mkstemp(suffix=".wav")[1])
        tts.synthesize(text, wav)
        h = detect_hallucinations(text, recog.recognize(load_slice(wav, None, None)))
        if h:
            any_hits += 1
            worst = max(worst, max(x["severity"] for x in h))
            if any(x["position"] > 0.7 for x in h):
                end_hits += 1
    return {"any": any_hits, "end": end_hits, "worst": round(worst, 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=10)
    args = ap.parse_args()
    tts, recog = get_tts_engine(), get_phoneme_recognizer()

    results = {"reps": args.reps, "series_a": [], "series_b": []}
    for series_key, series in (("series_a", SERIES_A), ("series_b", SERIES_B)):
        print(f"\n=== {series_key} ===", flush=True)
        for label, text in series:
            r = _rate(text, tts, recog, args.reps)
            r.update(label=label, text=text)
            results[series_key].append(r)
            print(f"  {label:22s}  any {r['any']:2d}/{args.reps}  "
                  f"end {r['end']:2d}/{args.reps}  worst {r['worst']:.2f}   …{text[-16:]!r}",
                  flush=True)
            OUT.write_text(json.dumps(results, indent=2))

    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
