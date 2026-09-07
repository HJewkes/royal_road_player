#!/usr/bin/env python3
"""Print book numbers with pending work, one per line — autopull's cheap precheck.

A book has work if any of:
  - the source offers a chapter not yet on disk (source chapter count > the number
    of on-disk chapters with raw.txt) — a newly published chapter to download,
  - disk holds a chapter with raw.txt but no normalized.txt — an interrupted prep
    from a prior run (mirrors autopull's find_new_chapters trigger so we don't
    strand a half-processed chapter), or
  - disk holds a chapter interrupted after normalize: chunked but missing chunk
    wavs, chunked never, or fully generated but never exported. See
    interrupted_stage() for how that is told apart from a completed chapter.

Only books at or beyond the highest book already on disk are considered, matching
autopull's discovery floor. This runs the upstream scraper but never imports
torch/TTS or boots the FastAPI backend, so autopull can gate expensive startup on
its output: empty stdout + exit 0 means there is nothing to do this cycle.

  pending_work.py <fiction_id>
      Book numbers with work, one per line (the precheck above).
  pending_work.py <fiction_id> --interrupted <book>
      "chapter:stage:wavs:texts" per interrupted chapter of that book, one per
      line. Filesystem only — no source fetch, so it never exits 3.

Exit codes:
  0  ran cleanly — stdout lists books with work (empty = nothing to do)
  2  bad usage
  3  source fetch failed — caller should fall back to a full run, not skip
"""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(SCRIPTS))

from source_books import resolve_source  # noqa: E402  (light import, no backend deps)


def _book_chapters_dir(fiction_dir: Path, book: int) -> Path:
    return fiction_dir / f"book_{book}" / "chapters"


def _on_disk_max_book(fiction_dir: Path) -> int:
    """Highest book_N on disk, or 0 if none."""
    highest = 0
    if fiction_dir.is_dir():
        for entry in fiction_dir.glob("book_*"):
            try:
                highest = max(highest, int(entry.name.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
    return highest


def _is_completed(chapter_dir: Path) -> bool:
    """True if metadata.json carries the durable completion marker.

    Export writes completed_at (discovery.mark_chapter_completed) and metadata.json
    outlives the intermediates, so a finished-then-pruned chapter — chunk wavs and
    audio.wav deleted to reclaim disk — stays distinguishable from one killed
    mid-TTS. Chapters exported before that marker existed have neither, but they
    all sit below autopull's book floor and are never examined here.
    """
    metadata = chapter_dir / "metadata.json"
    if not metadata.exists():
        return False
    try:
        with metadata.open() as f:
            return json.load(f).get("completed_at") is not None
    except (OSError, ValueError):
        return False


def _chunk_progress(chapter_dir: Path) -> tuple[int, int]:
    """Return (chunk_txt_count, chunk_wav_count) for a chapter."""
    chunks_dir = chapter_dir / "chunks"
    if not chunks_dir.is_dir():
        return 0, 0
    return len(list(chunks_dir.glob("*.txt"))), len(list(chunks_dir.glob("*.wav")))


def interrupted_stage(chapter_dir: Path) -> str | None:
    """The stage a chapter died at, or None if it needs no recovery.

    "chunk"     — normalized, but chunking never ran
    "generate"  — chunked, but at least one chunk still has no wav
    "export"    — every chunk has audio, but the export never completed
    """
    if not (chapter_dir / "normalized.txt").exists() or _is_completed(chapter_dir):
        return None
    texts, wavs = _chunk_progress(chapter_dir)
    if texts == 0:
        return "chunk"
    return "generate" if wavs < texts else "export"


def list_interrupted(chapters_dir: Path) -> list[tuple[int, str, int, int]]:
    """(chapter_number, stage, wavs, texts) for every interrupted chapter, in order."""
    if not chapters_dir.is_dir():
        return []
    found = []
    for chapter in chapters_dir.glob("chapter_*"):
        stage = interrupted_stage(chapter)
        if stage is None:
            continue
        try:
            number = int(chapter.name.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        texts, wavs = _chunk_progress(chapter)
        found.append((number, stage, wavs, texts))
    return sorted(found)


def _on_disk_stats(chapters_dir: Path) -> tuple[int, bool]:
    """Return (raw_txt_count, has_unfinished) for a book's chapters dir."""
    raw_count = 0
    has_unfinished = False
    if not chapters_dir.is_dir():
        return 0, False
    for chapter in chapters_dir.glob("chapter_*"):
        if not (chapter / "raw.txt").exists():
            continue
        raw_count += 1
        if not (chapter / "normalized.txt").exists():
            has_unfinished = True
        elif interrupted_stage(chapter) is not None:
            has_unfinished = True
    return raw_count, has_unfinished


def select_pending(source_counts: dict[int, int], fiction_dir: Path, floor: int) -> list[int]:
    """Books at/above the floor whose source is ahead of disk or that have an
    unfinished chapter left on disk."""
    candidates = {book for book in source_counts if book >= floor}
    if floor:
        candidates.add(floor)  # always re-check the newest on-disk book
    pending = []
    for book in sorted(candidates):
        raw_count, has_unfinished = _on_disk_stats(_book_chapters_dir(fiction_dir, book))
        if source_counts.get(book, 0) > raw_count or has_unfinished:
            pending.append(book)
    return pending


def _books_dir() -> Path:
    sys.path.insert(0, str(BACKEND))
    from src.config import get_settings

    return Path(get_settings().books_dir)


def report_interrupted(fiction_id: str, book: int) -> int:
    chapters_dir = _book_chapters_dir(_books_dir() / fiction_id, book)
    for number, stage, wavs, texts in list_interrupted(chapters_dir):
        print(f"{number}:{stage}:{wavs}:{texts}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) == 3 and argv[1] == "--interrupted":
        try:
            return report_interrupted(argv[0], int(argv[2]))
        except ValueError:
            print("usage: pending_work.py <fiction_id> --interrupted <book>", file=sys.stderr)
            return 2
    if len(argv) != 1:
        print("usage: pending_work.py <fiction_id> [--interrupted <book>]", file=sys.stderr)
        return 2
    fiction_id = argv[0]

    books_dir = _books_dir()  # also puts BACKEND on sys.path for the scraper import
    from src.scraper import get_scraper

    fiction_dir = books_dir / fiction_id
    floor = _on_disk_max_book(fiction_dir)

    source, fetch_fid = resolve_source(fiction_id, books_dir)
    try:
        chapters = get_scraper(source).get_chapter_list(fetch_fid, None)
    except Exception as exc:  # network / cookie / parse — let autopull fall back
        print(f"pending_work: source fetch failed: {exc}", file=sys.stderr)
        return 3

    source_counts: dict[int, int] = {}
    for chapter in chapters:
        book = chapter.get("book_number")
        if book is not None:
            source_counts[book] = source_counts.get(book, 0) + 1

    for book in select_pending(source_counts, fiction_dir, floor):
        print(book)
    return 0


if __name__ == "__main__":
    sys.exit(main())
