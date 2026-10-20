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

`--engine` (default: the configured engine) picks the engine and its chunker, and
the chapter is stamped with it. Chunk i renders with seed 999 + i.

`--batch` (Chatterbox only) renders the whole chapter through chatterbox-vllm
first, then re-renders the takes it truncated, babbled or failed on stock
Chatterbox with seed 999 + i. If chatterbox-vllm cannot run, the chapter
renders on stock.

  ./venv311/bin/python scripts/rerender_chapter.py 124774 7 16
  ./venv-cu128/bin/python scripts/rerender_chapter.py 124774 7 16 --engine chatterbox
  ./venv-cu128/bin/python scripts/rerender_chapter.py 124774 7 16 --engine chatterbox --batch
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.discovery import (  # noqa: E402
    get_chapter_discovery, get_chunk_discovery,
)
from src.export.concatenator import get_exporter  # noqa: E402
from src.text import (  # noqa: E402
    StatBlockConverter, TableConverter, TextChunker, TextNormalizer, chunking_for,
)
from src.tts import engine_stamp, get_tts_engine  # noqa: E402
from src.tts.batch import VllmBatchRenderer, render_chapter_batched  # noqa: E402
from src.tts.chatterbox import ChatterboxUnavailable  # noqa: E402
from src.tts.engines import ENGINES, chunk_seed  # noqa: E402
from src.tts.pool import RenderPool  # noqa: E402
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


def _progress(done: int, n: int, t0: float):
    if done % 10 == 0 or done == n:
        print(f"  synth {done}/{n}  ({time.time() - t0:.0f}s)", flush=True)


def _synthesize_inline(chunks, chunks_dir: Path, tts, verify: bool, t0: float):
    recognizer = get_phoneme_recognizer() if verify else None
    for done, chunk in enumerate(chunks, 1):
        out = chunks_dir / f"{chunk.index:03d}.wav"
        seed = chunk_seed(chunk.index)
        if recognizer is not None:
            synthesize_verified(tts, chunk.text, out, recognizer=recognizer, seed=seed)
        else:
            tts.synthesize(chunk.text, out, seed=seed)
        _progress(done, len(chunks), t0)


def _synthesize_pooled(chunks, chunks_dir: Path, engine: str, workers: int, verify: bool, t0: float):
    """Render through the production RenderPool, as /api/generate does."""
    settings = get_settings()
    pool = RenderPool(workers=workers, threads_per_worker=settings.tts_threads_per_worker,
                      verify=verify, retries=settings.verify_max_retries, engine=engine)
    try:
        with ThreadPoolExecutor(max_workers=workers) as feeders:
            futures = [
                feeders.submit(pool.render, c.text, chunks_dir / f"{c.index:03d}.wav", chunk_seed(c.index))
                for c in chunks
            ]
            for done, future in enumerate(as_completed(futures), 1):
                future.result()
                _progress(done, len(chunks), t0)
    finally:
        pool.shutdown()


def _synthesize_batched(chunks, chunks_dir: Path, tts, verify: bool):
    recognizer = get_phoneme_recognizer() if verify else None
    report = render_chapter_batched(
        [(c.index, c.text) for c in chunks], chunks_dir, VllmBatchRenderer(),
        stock_factory=lambda: tts, recognizer=recognizer, seed_for=chunk_seed,
    )
    if report.batch_failed:
        print(f"  batch failed, rendered on stock: {report.batch_failed}", flush=True)
    print(f"  batch {report.batch_s:.0f}s; {report.retake_count} stock retake(s) in "
          f"{report.retake_s:.0f}s: {report.retakes}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fiction_id")
    ap.add_argument("book", type=int)
    ap.add_argument("chapter", type=int)
    ap.add_argument("--format", default="mp3")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip self-healing (single take per chunk)")
    ap.add_argument("--engine", choices=ENGINES, default=None,
                    help="TTS engine (default: AUDIOBOOK_TTS_ENGINE)")
    ap.add_argument("--workers", type=int, default=1,
                    help="render through a RenderPool of this many workers (default: 1, inline)")
    ap.add_argument("--batch", action="store_true",
                    help="render through chatterbox-vllm, retaking flagged chunks on stock (chatterbox only)")
    args = ap.parse_args()
    fid, book, ch = args.fiction_id, args.book, args.chapter
    engine = args.engine or get_settings().tts_engine
    if args.batch and engine != "chatterbox":
        sys.exit("--batch renders Chatterbox only; pass --engine chatterbox")
    # Build the engine before anything is cleared, so a host that cannot run it
    # leaves the chapter's existing audio alone.
    try:
        tts = get_tts_engine(engine)
    except ChatterboxUnavailable as exc:
        sys.exit(f"Cannot render with {engine}: {exc}")

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

    chunk_results = TextChunker(chunking_for(engine)).chunk(text)
    chunksd.save_chunks(fid, book, ch, [(c.index, c.text) for c in chunk_results],
                        stamp=engine_stamp(engine))
    n = len(chunk_results)
    print(f"Chunked -> {n} chunks ({engine})", flush=True)

    # 3. Synthesize every chunk to its NNN.wav (self-healing unless --no-verify).
    chunks = chunksd.list_chunks(fid, book, ch)
    t0 = time.time()
    if args.batch:
        _synthesize_batched(chunks, chunks_dir, tts, not args.no_verify)
    elif args.workers > 1:
        _synthesize_pooled(chunks, chunks_dir, engine, args.workers, not args.no_verify, t0)
    else:
        _synthesize_inline(chunks, chunks_dir, tts, not args.no_verify, t0)

    # 4. Concatenate + export mp3 (overwrites the same episode path).
    path = get_exporter().export_chapter(fid, book, ch, args.format)
    if not path:
        sys.exit("Export failed")
    print(f"\nExported: {path}")
    print(f"Total synth time: {time.time() - t0:.0f}s for {n} chunks")


if __name__ == "__main__":
    main()
