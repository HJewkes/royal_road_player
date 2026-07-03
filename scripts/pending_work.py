#!/usr/bin/env python3
"""Print book numbers with pending work, one per line — autopull's cheap precheck.

A book has work if either:
  - the source offers a chapter not yet on disk (source chapter count > the number
    of on-disk chapters with raw.txt) — a newly published chapter to download, or
  - disk holds a chapter with raw.txt but no normalized.txt — an interrupted prep
    from a prior run (mirrors autopull's find_new_chapters trigger so we don't
    strand a half-processed chapter).

Only books at or beyond the highest book already on disk are considered, matching
autopull's discovery floor. This runs the upstream scraper but never imports
torch/TTS or boots the FastAPI backend, so autopull can gate expensive startup on
its output: empty stdout + exit 0 means there is nothing to do this cycle.

Exit codes:
  0  ran cleanly — stdout lists books with work (empty = nothing to do)
  2  bad usage
  3  source fetch failed — caller should fall back to a full run, not skip
"""
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


def _on_disk_stats(chapters_dir: Path) -> tuple[int, bool]:
    """Return (raw_txt_count, has_unprocessed) for a book's chapters dir."""
    raw_count = 0
    has_unprocessed = False
    if not chapters_dir.is_dir():
        return 0, False
    for chapter in chapters_dir.glob("chapter_*"):
        if not (chapter / "raw.txt").exists():
            continue
        raw_count += 1
        if not (chapter / "normalized.txt").exists():
            has_unprocessed = True
    return raw_count, has_unprocessed


def select_pending(source_counts: dict[int, int], fiction_dir: Path, floor: int) -> list[int]:
    """Books at/above the floor whose source is ahead of disk or that have an
    unprocessed chapter left on disk."""
    candidates = {book for book in source_counts if book >= floor}
    if floor:
        candidates.add(floor)  # always re-check the newest on-disk book
    pending = []
    for book in sorted(candidates):
        raw_count, has_unprocessed = _on_disk_stats(_book_chapters_dir(fiction_dir, book))
        if source_counts.get(book, 0) > raw_count or has_unprocessed:
            pending.append(book)
    return pending


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: pending_work.py <fiction_id>", file=sys.stderr)
        return 2
    fiction_id = sys.argv[1]

    sys.path.insert(0, str(BACKEND))
    from src.config import get_settings
    from src.scraper import get_scraper

    books_dir = Path(get_settings().books_dir)
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
