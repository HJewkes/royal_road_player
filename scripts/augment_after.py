#!/usr/bin/env python3
"""Measure each demo clip's phoneme distance so before/after claims are honest.

Runs the phoneme model directly on the embedded before/after mp3 clips and scores
each against the intended word's G2P, so the page can show whether a respelling
actually moved the pronunciation closer (or not). No XTTS needed.
"""
import base64
import io
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.validation.phonemes import (  # noqa: E402
    clean_ipa, g2p, get_phoneme_recognizer, phoneme_distance,
)

DATA = BACKEND.parent / "logs" / "demo_data.json"


def _clip_phones(b64, recog):
    from pydub import AudioSegment
    import numpy as np
    seg = AudioSegment.from_mp3(io.BytesIO(base64.b64decode(b64)))
    seg = seg.set_frame_rate(16000).set_channels(1)
    samples = np.array(seg.get_array_of_samples(), dtype="float32") / 32768.0
    return recog.recognize(samples)


def main():
    rows = json.loads(DATA.read_text())
    recog = get_phoneme_recognizer()
    for r in rows:
        expected = g2p(r["word"])
        for side in ("before", "after"):
            b64 = r.get(f"{side}_mp3")
            if not b64:
                continue
            phones = _clip_phones(b64, recog)
            r[f"{side}_clip_dist"] = round(phoneme_distance(expected, phones), 3)
        b, a = r.get("before_clip_dist"), r.get("after_clip_dist")
        print(f"  {r['word']:<13} before_clip={b} after_clip={a}"
              + (f"  -> {'IMPROVED' if a is not None and a < b - 0.03 else 'no gain'}"
                 if a is not None else ""))
    DATA.write_text(json.dumps(rows, indent=2))
    print(f"Updated {DATA}")


if __name__ == "__main__":
    main()
