#!/usr/bin/env python3
"""Hardened chunk-ending probe: multiple base sentences + digit-vs-spelled numbers.

Follows up the single-sentence punctuation probe. Two questions:

  1. Does ANY base sentence (easy / place-name / dense roster-like) babble on a
     punctuation ending? (tests whether punctuation is ever the trigger)
  2. Is the number-ending trigger the DIGIT GLYPH or the number itself? i.e. does
     "up 11." babble while "up eleven." does not? (if so, spelling out trailing
     numbers is a clean deterministic fix, no re-roll needed)

  ./venv311/bin/python scripts/ending_probe.py [--reps 10]
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

OUT = ROOT / "logs" / "ending_probe.json"

PUNCT_BASES = [
    ("easy", "He nodded slowly and told the whole team to keep their heads up"),
    ("name", "The Chester crowd roared as the ball curled into the top corner at the Deva"),
    ("dense", "Number twelve, Magnus Evergreen, a versatile defender and defensive midfielder"),
]
# (label, how to build the ending from a base)
PUNCT_VARIANTS = [
    ("period .",  lambda b: b + "."),
    ("quoted .\"", lambda b: '"' + b + '."'),
    ("bare \"",   lambda b: b + '"'),
    ("none",      lambda b: b),
    ("exclaim !", lambda b: b + "!"),
    ("ellipsis …", lambda b: b + "…"),
]

# The crux: same content, digit vs spelled-out trailing number.
NUMBER_TESTS = [
    ("digit  …to 16.",    "He nodded slowly and they moved the score along to 16."),
    ("spelled …to sixteen.", "He nodded slowly and they moved the score along to sixteen."),
    ("digit  …up 11.",    "PA one hundred sixty-five, CA one hundred fifty-two, up 11."),
    ("spelled …up eleven.", "PA one hundred sixty-five, CA one hundred fifty-two, up eleven."),
    ("digit  …with 7.",   "The striker had a fine game and finished the night with 7."),
    ("spelled …with seven.", "The striker had a fine game and finished the night with seven."),
    ("digit  …to 113.",   "The youth academy intake this year rose to 113."),
    ("spelled …to one hundred thirteen.", "The youth academy intake this year rose to one hundred thirteen."),
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
    results = {"reps": args.reps, "punctuation": [], "numbers": []}

    print("=== punctuation across bases ===", flush=True)
    for base_label, base in PUNCT_BASES:
        for var_label, build in PUNCT_VARIANTS:
            text = build(base)
            r = _rate(text, tts, recog, args.reps)
            r.update(base=base_label, variant=var_label)
            results["punctuation"].append(r)
            print(f"  {base_label:5s} {var_label:11s}  any {r['any']:2d}/{args.reps}  "
                  f"end {r['end']:2d}/{args.reps}  worst {r['worst']:.2f}", flush=True)
            OUT.write_text(json.dumps(results, indent=2))

    print("\n=== digit vs spelled number endings ===", flush=True)
    for label, text in NUMBER_TESTS:
        r = _rate(text, tts, recog, args.reps)
        r.update(label=label)
        results["numbers"].append(r)
        print(f"  {label:34s}  any {r['any']:2d}/{args.reps}  "
              f"end {r['end']:2d}/{args.reps}  worst {r['worst']:.2f}", flush=True)
        OUT.write_text(json.dumps(results, indent=2))

    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
