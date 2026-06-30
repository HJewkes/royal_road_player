#!/usr/bin/env python3
"""List book numbers available at a fiction's upstream source, one per line.

Honors patreon_meta.json so a Royal-Road-style numeric fiction_id that is
actually sourced from Patreon resolves to its Patreon campaign — mirroring the
download worker's _detect_source bridging. autopull.sh uses this to discover
books beyond the highest one already on disk (e.g. a freshly started Book 8).

Prints nothing and exits non-zero on failure so the caller can fall back to
its on-disk view rather than skipping a run.
"""
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _parse_patreon_fid(url: str) -> str | None:
    """patreon.com/c/<slug>/... -> patreon_<slug> (the scraper's fiction_id)."""
    match = re.search(r"patreon\.com/c/([^/]+)", url)
    return f"patreon_{match.group(1)}" if match else None


def resolve_source(fiction_id: str, books_dir: Path) -> tuple[str, str]:
    """Return (scraper_source, fetch_fiction_id) for a fiction_id."""
    if fiction_id.startswith("patreon_"):
        return "patreon", fiction_id
    meta_path = books_dir / fiction_id / "patreon_meta.json"
    if meta_path.exists():
        url = json.loads(meta_path.read_text()).get("patreon_url", "")
        patreon_fid = _parse_patreon_fid(url)
        if patreon_fid:
            return "patreon", patreon_fid
    return "royal_road", fiction_id


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: source_books.py <fiction_id>", file=sys.stderr)
        return 2
    fiction_id = sys.argv[1]
    sys.path.insert(0, str(BACKEND))
    from src.config import get_settings
    from src.scraper import get_scraper

    source, fetch_fid = resolve_source(fiction_id, get_settings().books_dir)
    chapters = get_scraper(source).get_chapter_list(fetch_fid, None)
    books = sorted({
        ch["book_number"] for ch in chapters if ch.get("book_number") is not None
    })
    for book in books:
        print(book)
    return 0


if __name__ == "__main__":
    sys.exit(main())
