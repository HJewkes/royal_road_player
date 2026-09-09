#!/usr/bin/env python3
"""Fill in audio_duration_seconds for chapters completed before it was recorded.

Duration is probed from the chapter's exported file, which survives the disk
cleanup that removes audio.wav and the chunk wavs. Chapters whose export is also
gone are reported and skipped — there is nothing left to measure.

  ./venv311/bin/python scripts/backfill_durations.py --dry-run
  ./venv311/bin/python scripts/backfill_durations.py
  ./venv311/bin/python scripts/backfill_durations.py 124774 8
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent / "backend"))

from src.config import get_settings  # noqa: E402
from src.discovery import ChapterDiscovery  # noqa: E402
from src.export.concatenator import probe_duration_seconds  # noqa: E402

_discovery = ChapterDiscovery()


def _chapters(books_dir: Path, fiction_id: str | None, book: int | None):
    """Yield metadata.json paths for chapters, newest book last."""
    pattern = f"{fiction_id or '*'}/book_{book if book is not None else '*'}"
    for meta in sorted(books_dir.glob(f"{pattern}/chapters/chapter_*/metadata.json")):
        yield meta


def _export_for(meta_path: Path, data: dict) -> Path | None:
    """The chapter's export, from metadata if recorded or by naming convention."""
    recorded = data.get("export_path")
    if recorded and Path(recorded).exists():
        return Path(recorded)
    chapter = meta_path.parent
    return _discovery.find_export(
        chapter.parents[2].name,
        int(chapter.parents[1].name.split("_")[1]),
        int(chapter.name.split("_")[1]),
    )


def backfill(meta_path: Path, dry_run: bool) -> str:
    """Return a one-word outcome for this chapter."""
    try:
        data = json.loads(meta_path.read_text())
    except Exception as e:
        print(f"  ! unreadable {meta_path}: {e}")
        return "error"

    had_chunk_count = "chunk_count" in data
    if data.get("audio_duration_seconds") is not None and not had_chunk_count:
        return "ok"

    duration = data.get("audio_duration_seconds")
    if duration is None:
        export = _export_for(meta_path, data)
        if export is None:
            return "no-export"
        duration = probe_duration_seconds(export)
        if duration is None:
            return "unprobeable"

    if dry_run:
        print(f"  would set {meta_path.parent.name}: {duration:.1f}s"
              + (" (and drop chunk_count)" if had_chunk_count else ""))
        return "would-fix"

    data["audio_duration_seconds"] = round(duration, 3)
    data.pop("chunk_count", None)
    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.replace(meta_path)
    print(f"  {meta_path.parent.name}: {duration:.1f}s")
    return "fixed"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fiction_id", nargs="?")
    ap.add_argument("book", nargs="?", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    counts: dict[str, int] = {}
    for meta in _chapters(get_settings().books_dir, args.fiction_id, args.book):
        outcome = backfill(meta, args.dry_run)
        counts[outcome] = counts.get(outcome, 0) + 1

    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
