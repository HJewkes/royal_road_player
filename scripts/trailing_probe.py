#!/usr/bin/env python3
"""Probe whether a trailing closing-quote causes XTTS's end-of-chunk babble.

Most trailing hallucinations land on chunks ending in `."` (dialogue close).
This synthesizes such chunks as-is vs with the trailing quote stripped, a few
times each, and measures how often a hallucinated outburst appears — to confirm
the trigger and validate a chunk-ending normalization fix.

  ./venv311/bin/python scripts/trailing_probe.py
"""
import re
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)

CHUNKS = [(7, 3, 135), (6, 14, 79), (7, 3, 349)]
REPS = 3


def _strip_trailing_quote(text):
    t = text.rstrip()
    t = re.sub(r'["“”‘’\']+$', "", t).rstrip()
    return t


def _rate(text, tts, recog):
    hits, worst = 0, 0.0
    for _ in range(REPS):
        wav = Path(tempfile.mkstemp(suffix=".wav")[1])
        tts.synthesize(text, wav)
        halluc = detect_hallucinations(text, recog.recognize(load_slice(wav, None, None)))
        if halluc:
            hits += 1
            worst = max(worst, max(h["severity"] for h in halluc))
    return hits, worst


def main():
    disc, tts, recog = ChunkDiscovery(), get_tts_engine(), get_phoneme_recognizer()
    print(f"Trailing-quote probe, {REPS} reps each\n")
    base_hits = fix_hits = 0
    for book, ch, idx in CHUNKS:
        c = disc.get_chunk("124774", book, ch, idx)
        as_is = c.text.rstrip()
        stripped = _strip_trailing_quote(c.text)
        bh, bw = _rate(as_is, tts, recog)
        fh, fw = _rate(stripped, tts, recog)
        base_hits += bh
        fix_hits += fh
        print(f"  b{book}/ch{ch}/{idx:03d}  ends {as_is[-18:]!r}")
        print(f"       as-is:          hallucinated {bh}/{REPS} (worst {bw:.2f})")
        print(f"       quote stripped: hallucinated {fh}/{REPS} (worst {fw:.2f})")
    n = len(CHUNKS) * REPS
    print(f"\nTOTAL  as-is {base_hits}/{n}   quote-stripped {fix_hits}/{n}")


if __name__ == "__main__":
    main()
