#!/usr/bin/env python3
"""Wide scan for hallucinated audio — anything the TTS injected that isn't in the text.

Runs on EVERY rendered chunk (not just ones with a word-level defect). Two signals:

  1. Injected phonemes — phoneme-align the chunk's expected pronunciation (espeak G2P)
     against what a vocab-free wav2vec2 model actually hears; any run of >=5 audio
     phones with no matching source text is a phantom outburst (babble between words).
  2. Injected waveform — audio markedly longer than the text warrants (extra sound the
     phoneme model may not even voice: buzzes, repeats, long non-speech). A cheap,
     model-free duration-ratio check that complements the phonetic signal.

Phoneme results are cached by wav hash, so chapters already triaged rescan fast.

  ./venv311/bin/python scripts/scan_hallucinations.py 124774 7 3      # one chapter
  ./venv311/bin/python scripts/scan_hallucinations.py --all --json logs/halluc.json
"""
import argparse
import json
import sys
import wave
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.discovery import ChunkDiscovery  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    clean_ipa, detect_hallucinations, g2p, get_phoneme_recognizer,
)

PHONES_PER_SEC = 13.0        # rough XTTS speaking rate
DURATION_RATIO_FLAG = 1.45   # audio this much longer than expected = injected waveform


def _iter_chapters(books_dir, only):
    if only:
        yield only
        return
    for d in sorted(books_dir.glob("*/book_*/chapters/chapter_*/chunks")):
        if any(d.glob("*.wav")):
            ch = d.parent
            yield ch.parents[2].name, int(ch.parents[1].name.split("_")[1]), int(ch.name.split("_")[1])


def _wav_seconds(path):
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return None


def _duration_ratio(chunk_text, wav_path):
    """Audio seconds / expected speech seconds; >1 means longer than the text warrants."""
    secs = _wav_seconds(wav_path)
    expected_phones = len(clean_ipa(g2p(chunk_text)))
    if not secs or not expected_phones:
        return None
    return round(secs / (expected_phones / PHONES_PER_SEC), 2)


def _scan_chapter(fid, book, ch, disc, recog):
    findings = []
    chunks = [c for c in disc.list_chunks(fid, book, ch) if c.has_audio]
    for chunk in chunks:
        phones = recog.recognize_wav(chunk.audio_path)
        halluc = detect_hallucinations(chunk.text, phones)
        ratio = _duration_ratio(chunk.text, chunk.audio_path)
        stretched = ratio is not None and ratio >= DURATION_RATIO_FLAG
        if not halluc and not stretched:
            continue
        findings.append({
            "book": book, "chapter": ch, "chunk": chunk.index,
            "wav": str(chunk.audio_path),
            "phonetic": [{"phones": h["phones"], "length": h["length"],
                          "position": h["position"], "severity": h["severity"]} for h in halluc],
            "duration_ratio": ratio, "stretched": stretched,
            "text": " ".join(chunk.text.split())[:160],
        })
    return findings, len(chunks)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="*", help="fiction_id book chapter")
    ap.add_argument("--all", action="store_true", help="scan every chapter with audio")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--limit", type=int, default=25, help="rows to print")
    args = ap.parse_args()

    only = None
    if args.target:
        if len(args.target) != 3:
            ap.error("target must be: fiction_id book chapter")
        only = (args.target[0], int(args.target[1]), int(args.target[2]))
    elif not args.all:
        ap.error("give a target chapter or --all")

    disc, recog = ChunkDiscovery(), get_phoneme_recognizer()
    all_findings, chapters, chunks = [], 0, 0
    for fid, book, ch in _iter_chapters(get_settings().books_dir, only):
        chapters += 1
        print(f"Scanning b{book}/ch{ch} …", flush=True)
        found, n = _scan_chapter(fid, book, ch, disc, recog)
        chunks += n
        all_findings.extend(found)

    phon = [f for f in all_findings if f["phonetic"]]
    stretched = [f for f in all_findings if f["stretched"]]
    print(f"\nScanned {chapters} chapter(s), {chunks} chunks.")
    print(f"Injected phonemes: {len(phon)} chunks ({100*len(phon)/chunks:.1f}%)  |  "
          f"stretched waveform: {len(stretched)} chunks" if chunks else "")

    ranked = sorted(phon, key=lambda f: -max((p["severity"] for p in f["phonetic"]), default=0))
    print(f"\nTop {min(args.limit, len(ranked))} injected-phoneme outbursts:\n")
    for f in ranked[:args.limit]:
        p = max(f["phonetic"], key=lambda x: x["length"])
        print(f"  b{f['book']}/ch{f['chapter']}/{f['chunk']:03d} @pos {p['position']}  "
              f"/{p['phones']}/ (len {p['length']}, ratio {f['duration_ratio']})")
        print(f"        …{f['text'][:110]}…")

    if args.json:
        args.json.write_text(json.dumps(all_findings, indent=2))
        print(f"\nWrote {len(all_findings)} findings to {args.json}")


if __name__ == "__main__":
    main()
