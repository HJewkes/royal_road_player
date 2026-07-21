#!/usr/bin/env python3
"""Post-render clean pass: re-roll only the chunks whose audio babbles, then re-export.

XTTS sometimes emits a phantom outburst at a chunk boundary (most visibly at the
END of a short chunk — e.g. a roster row ending "…up 16." picking up a stray
"tall"). This scans every rendered chunk with the vocab-free phoneme hallucination
detector and, for any chunk that babbles, re-synthesizes it up to N times keeping
the first clean take (else the least-bad). Only babbling chunks are touched; the
rest keep their shipped audio. Then it re-concatenates and re-exports the mp3.

Run after a chapter has been rendered, when the GPU is free:
  ./venv311/bin/python scripts/clean_chapter.py 124774 7 16 [--tries 6] [--no-export]
"""
import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import get_chunk_discovery  # noqa: E402
from src.export.concatenator import get_exporter  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)


def _worst(halluc):
    return max((h["severity"] for h in halluc), default=0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fiction_id")
    ap.add_argument("book", type=int)
    ap.add_argument("chapter", type=int)
    ap.add_argument("--tries", type=int, default=6, help="max re-rolls per babbling chunk")
    ap.add_argument("--no-export", action="store_true")
    args = ap.parse_args()
    fid, book, ch = args.fiction_id, args.book, args.chapter

    disc = get_chunk_discovery()
    tts, recog = get_tts_engine(), get_phoneme_recognizer()
    chunks = [c for c in disc.list_chunks(fid, book, ch) if c.has_audio]
    print(f"Scanning {len(chunks)} chunks for babble…", flush=True)

    flagged = []
    for c in chunks:
        h = detect_hallucinations(c.text, recog.recognize_wav(c.audio_path))
        if h:
            flagged.append((c, _worst(h)))
    print(f"{len(flagged)} chunk(s) babble; re-rolling up to {args.tries}× each.\n", flush=True)

    cleaned = improved = 0
    for c, base_sev in flagged:
        best_path, best_sev = None, base_sev
        clean = False
        for _ in range(args.tries):
            tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
            tts.synthesize(c.text, tmp)
            h = detect_hallucinations(c.text, recog.recognize(load_slice(tmp, None, None)))
            sev = _worst(h)
            if not h:
                best_path, best_sev, clean = tmp, 0.0, True
                break
            if sev < best_sev:
                best_path, best_sev = tmp, sev
        if best_path is not None:
            # overwrite the chunk's shipped wav with the cleaner take
            import shutil
            shutil.copy(best_path, c.audio_path)
            cleaned += 1 if clean else 0
            improved += 1
        status = "clean" if clean else (f"improved {base_sev:.2f}->{best_sev:.2f}"
                                        if best_path is not None else "no better take")
        print(f"  ch{c.index:03d}: {status}", flush=True)

    print(f"\n{cleaned}/{len(flagged)} now clean, {improved} replaced.")

    if flagged and not args.no_export:
        chapter_dir = disc.get_chunks_dir(fid, book, ch).parent
        for stale in (chapter_dir / "audio.wav", chapter_dir / "concat_list.txt"):
            if stale.exists():
                stale.unlink()
        path = get_exporter().export_chapter(fid, book, ch, "mp3")
        print(f"Re-exported: {path}" if path else "Export failed")


if __name__ == "__main__":
    main()
