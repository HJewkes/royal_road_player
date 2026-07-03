"""Tests for autopull's cheap precheck (scripts/pending_work.py).

Covers the pure source-vs-disk decision logic — no scraper/network. This is the
gate that decides whether a 15-minute poll boots the backend at all, so its
"nothing to do" answer needs to be trustworthy and its "work exists" answer must
not strand a new or half-processed chapter.
"""
import importlib.util
from pathlib import Path

_HELPER = Path(__file__).resolve().parents[2] / "scripts" / "pending_work.py"
_spec = importlib.util.spec_from_file_location("pending_work", _HELPER)
pending_work = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pending_work)


def _make_book(fiction_dir: Path, book: int, n_raw: int, n_normalized: int) -> None:
    """Create book_<book> with n_raw chapters (raw.txt); the first n_normalized of
    them also get normalized.txt."""
    chapters = fiction_dir / f"book_{book}" / "chapters"
    chapters.mkdir(parents=True)
    for i in range(1, n_raw + 1):
        chapter = chapters / f"chapter_{i}"
        chapter.mkdir()
        (chapter / "raw.txt").write_text("x")
        if i <= n_normalized:
            (chapter / "normalized.txt").write_text("y")


def test_on_disk_max_book(tmp_path):
    assert pending_work._on_disk_max_book(tmp_path) == 0
    _make_book(tmp_path, 6, 3, 3)
    _make_book(tmp_path, 7, 2, 2)
    assert pending_work._on_disk_max_book(tmp_path) == 7


def test_on_disk_stats_counts_raw_and_flags_unprocessed(tmp_path):
    _make_book(tmp_path, 7, 3, 3)
    chapters = tmp_path / "book_7" / "chapters"
    assert pending_work._on_disk_stats(chapters) == (3, False)


def test_on_disk_stats_missing_dir(tmp_path):
    assert pending_work._on_disk_stats(tmp_path / "nope") == (0, False)


def test_on_disk_stats_ignores_chapter_without_raw(tmp_path):
    _make_book(tmp_path, 7, 2, 2)
    (tmp_path / "book_7" / "chapters" / "chapter_3").mkdir()  # dir, no raw.txt
    assert pending_work._on_disk_stats(tmp_path / "book_7" / "chapters") == (2, False)


def test_select_pending_new_source_chapter(tmp_path):
    """Source has 12, disk has 11 -> book has work."""
    _make_book(tmp_path, 7, 11, 11)
    assert pending_work.select_pending({6: 15, 7: 12}, tmp_path, floor=7) == [7]


def test_select_pending_caught_up(tmp_path):
    _make_book(tmp_path, 7, 11, 11)
    assert pending_work.select_pending({6: 15, 7: 11}, tmp_path, floor=7) == []


def test_select_pending_brand_new_book(tmp_path):
    """A freshly started Book 8 has no dir yet -> flagged."""
    _make_book(tmp_path, 7, 11, 11)
    assert pending_work.select_pending({7: 11, 8: 3}, tmp_path, floor=7) == [8]


def test_select_pending_interrupted_prep(tmp_path):
    """Chapter downloaded but not normalized -> work even if source count matches."""
    _make_book(tmp_path, 7, 11, 10)  # 11 raw, only 10 normalized
    assert pending_work.select_pending({7: 11}, tmp_path, floor=7) == [7]


def test_select_pending_ignores_books_below_floor(tmp_path):
    _make_book(tmp_path, 7, 11, 11)
    # Book 6 is behind the floor and irrelevant even if source lists more for it.
    assert pending_work.select_pending({6: 99, 7: 11}, tmp_path, floor=7) == []
