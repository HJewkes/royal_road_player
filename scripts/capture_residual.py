#!/usr/bin/env python3
"""Capture the actual post-fix babble audio for the residual hallucination chunks.

The rechunk/rebuild test only saved the CLEAN take for chunks it fully fixed; the
residual chunks (fix_hits > 0) still babble sometimes but their babbling audio was
never kept. This regenerates each residual chunk's rebuilt text a few times and
saves the first take that actually hallucinates (with the detected phones/position),
so the report's residual tab can play the real post-fix babble instead of the
pre-fix shipped reference.

Writes logs/residual_capture.json keyed "book_chapter_chunk". Reuses the wavs in
logs/residual_clips/. Run after any other XTTS job frees the GPU.

  ./venv311/bin/python scripts/capture_residual.py [--reps 6]
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

from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)

TEST = ROOT / "logs" / "rechunk_test.json"
OUT = ROOT / "logs" / "residual_capture.json"
CLIPS = ROOT / "logs" / "residual_clips"


def _concat(paths, out):
    with wave.open(str(paths[0])) as w0:
        params = w0.getparams()
    with wave.open(str(out), "wb") as wout:
        wout.setparams(params)
        for p in paths:
            with wave.open(str(p)) as w:
                wout.writeframes(w.readframes(w.getnframes()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=6, help="max regen attempts per chunk")
    args = ap.parse_args()

    residual = [r for r in json.loads(TEST.read_text())["results"] if r["fix_hits"] > 0]
    residual.sort(key=lambda r: -r["fix_hits"])
    CLIPS.mkdir(parents=True, exist_ok=True)
    tts, recog = get_tts_engine(), get_phoneme_recognizer()

    out = {}
    if OUT.exists():
        out = json.loads(OUT.read_text())

    for i, r in enumerate(residual, 1):
        key = f"{r['book']}_{r['chapter']}_{r['chunk']}"
        if key in out and Path(out[key]["wav"]).exists():
            continue
        best = None  # (wav_paths, phones, position)
        fallback = None
        for _ in range(args.reps):
            wavs, halluc = [], []
            for t in r["new_texts"]:
                w = Path(tempfile.mkstemp(suffix=".wav")[1])
                tts.synthesize(t, w)
                wavs.append(w)
                halluc.extend(detect_hallucinations(t, recog.recognize(load_slice(w, None, None))))
            fallback = wavs
            if halluc:
                worst = max(halluc, key=lambda h: h["length"])
                best = (wavs, worst["phones"], worst["position"])
                break
        wavs, phones, pos, reproduced = (
            (*best, True) if best else (fallback, r["phones"], r["position"], False)
        )
        dest = CLIPS / f"{key}.wav"
        _concat(wavs, dest)
        out[key] = {"wav": str(dest), "phones": phones, "position": pos,
                    "reproduced": reproduced, "reps": args.reps}
        OUT.write_text(json.dumps(out, indent=2))
        print(f"[{i}/{len(residual)}] {key}  "
              f"{'babble captured' if reproduced else 'not reproduced (kept last take)'}"
              f"  /{phones}/", flush=True)

    got = sum(1 for v in out.values() if v["reproduced"])
    print(f"\nCaptured {got}/{len(out)} residual babbles ({len(out)-got} not reproduced).")


if __name__ == "__main__":
    main()
