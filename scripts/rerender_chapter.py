#!/usr/bin/env python3
"""Re-render one chapter end-to-end through the production text+audio pipeline.

Re-runs normalize -> chunk -> synthesize -> export for a single chapter, reusing
the exact production components (TableConverter + StatBlockConverter +
TextNormalizer, TextChunker, the TTS engine, AudioExporter). Used to regenerate a
chapter after a normalization/chunking change without standing up the API+worker.

It clears the chapter's stale chunk audio and audio.wav first so every new chunk
is freshly synthesized and the export re-concatenates from scratch. The export
overwrites the same mp3 path, so a subsequent publish_feed run targets the same
episode.

  ./venv311/bin/python scripts/rerender_chapter.py 124774 7 16
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import (  # noqa: E402
    get_chapter_discovery, get_chunk_discovery,
)
from src.export.concatenator import get_exporter  # noqa: E402
from src.text import (  # noqa: E402
    StatBlockConverter, TableConverter, TextChunker, TextNormalizer,
)
from src.tts import get_tts_engine  # noqa: E402
from src.tts.verified import synthesize_verified  # noqa: E402
from src.validation.phonemes import get_phoneme_recognizer  # noqa: E402


def _clear_chunk_artifacts(chunks_dir: Path, chapter_dir: Path):
    """Remove stale chunk audio/text and the concatenated wav so nothing lingers."""
    if chunks_dir.exists():
        for f in chunks_dir.glob("*"):
            if f.suffix in {".wav", ".txt", ".error"}:
                f.unlink()
    for stale in (chapter_dir / "audio.wav", chapter_dir / "concat_list.txt"):
        if stale.exists():
            stale.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fiction_id")
    ap.add_argument("book", type=int)
    ap.add_argument("chapter", type=int)
    ap.add_argument("--format", default="mp3")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip self-healing (single take per chunk)")
    args = ap.parse_args()
    fid, book, ch = args.fiction_id, args.book, args.chapter

    chapters = get_chapter_discovery()
    chunksd = get_chunk_discovery()

    raw = chapters.get_raw_text(fid, book, ch)
    if not raw:
        sys.exit(f"No raw text for {fid} b{book}/ch{ch}")

    # 1. Normalize through the full production text pipeline.
    text = TableConverter().convert(raw)
    text = StatBlockConverter().convert(text)
    text = TextNormalizer().normalize(text)
    chapters.save_normalized_text(fid, book, ch, text)
    print(f"Normalized -> {len(text)} chars", flush=True)

    # 2. Clear stale artifacts, then re-chunk.
    chunks_dir = chunksd.get_chunks_dir(fid, book, ch)
    chapter_dir = chunks_dir.parent
    _clear_chunk_artifacts(chunks_dir, chapter_dir)

    chunk_results = TextChunker().chunk(text)
    chunksd.save_chunks(fid, book, ch, [(c.index, c.text) for c in chunk_results])
    n = len(chunk_results)
    print(f"Chunked -> {n} chunks", flush=True)

    # 3. Synthesize every chunk to its NNN.wav (self-healing unless --no-verify).
    tts = get_tts_engine()
    recognizer = None if args.no_verify else get_phoneme_recognizer()
    t0 = time.time()
    for chunk in chunksd.list_chunks(fid, book, ch):
        out = chunks_dir / f"{chunk.index:03d}.wav"
        if recognizer is not None:
            synthesize_verified(tts, chunk.text, out, recognizer=recognizer)
        else:
            tts.synthesize(chunk.text, out)
        if chunk.index % 10 == 0 or chunk.index == n:
            elapsed = time.time() - t0
            print(f"  synth {chunk.index}/{n}  ({elapsed:.0f}s)", flush=True)

    # 4. Concatenate + export mp3 (overwrites the same episode path).
    path = get_exporter().export_chapter(fid, book, ch, args.format)
    if not path:
        sys.exit("Export failed")
    print(f"\nExported: {path}")
    print(f"Total synth time: {time.time() - t0:.0f}s for {n} chunks")


if __name__ == "__main__":
    main()
