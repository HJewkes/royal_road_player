"""Tests for autopull's cheap precheck (scripts/pending_work.py).

Covers the pure source-vs-disk decision logic — no scraper/network. This is the
gate that decides whether a 15-minute poll boots the backend at all, so its
"nothing to do" answer needs to be trustworthy and its "work exists" answer must
not strand a new or half-processed chapter.
"""
import importlib.util
import json
from pathlib import Path

_HELPER = Path(__file__).resolve().parents[2] / "scripts" / "pending_work.py"
_spec = importlib.util.spec_from_file_location("pending_work", _HELPER)
pending_work = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pending_work)


def _make_book(fiction_dir: Path, book: int, n_raw: int, n_normalized: int) -> None:
    """Create book_<book> with n_raw chapters (raw.txt); the first n_normalized of
    them also get normalized.txt plus the completion marker export writes, so they
    look like finished chapters whose intermediates were pruned."""
    chapters = fiction_dir / f"book_{book}" / "chapters"
    chapters.mkdir(parents=True)
    for i in range(1, n_raw + 1):
        chapter = chapters / f"chapter_{i}"
        chapter.mkdir()
        (chapter / "raw.txt").write_text("x")
        if i <= n_normalized:
            (chapter / "normalized.txt").write_text("y")
            _mark_completed(chapter)


def _mark_completed(chapter_dir: Path) -> None:
    (chapter_dir / "metadata.json").write_text(
        json.dumps({"chapter_number": 1, "title": "t", "completed_at": "2026-08-31T15:06:49"})
    )


def _make_chunks(chapter_dir: Path, n_texts: int, n_wavs: int) -> None:
    chunks = chapter_dir / "chunks"
    chunks.mkdir(exist_ok=True)
    for i in range(1, n_texts + 1):
        (chunks / f"{i}.txt").write_text("chunk")
        if i <= n_wavs:
            (chunks / f"{i}.wav").write_bytes(b"RIFF")


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


def _chapter(tmp_path: Path, book: int, number: int) -> Path:
    return tmp_path / f"book_{book}" / "chapters" / f"chapter_{number}"


def test_interrupted_stage_generate(tmp_path):
    """Killed mid-TTS: chunk texts on disk, only some of them have a wav."""
    _make_book(tmp_path, 7, 11, 10)
    chapter = _chapter(tmp_path, 7, 11)
    (chapter / "normalized.txt").write_text("y")
    _make_chunks(chapter, 456, 205)
    assert pending_work.interrupted_stage(chapter) == "generate"


def test_interrupted_stage_chunk(tmp_path):
    """Killed between normalize and chunk: no chunks at all."""
    _make_book(tmp_path, 7, 11, 10)
    chapter = _chapter(tmp_path, 7, 11)
    (chapter / "normalized.txt").write_text("y")
    assert pending_work.interrupted_stage(chapter) == "chunk"


def test_interrupted_stage_export(tmp_path):
    """Every chunk has audio but the export never marked the chapter complete."""
    _make_book(tmp_path, 7, 11, 10)
    chapter = _chapter(tmp_path, 7, 11)
    (chapter / "normalized.txt").write_text("y")
    _make_chunks(chapter, 12, 12)
    assert pending_work.interrupted_stage(chapter) == "export"


def test_interrupted_stage_ignores_pruned_completed_chapter(tmp_path):
    """Completed chapter whose chunk wavs were pruned: texts remain, wavs are gone.

    Byte-for-byte the same on-disk shape as a chapter killed at chunk 0, so only
    the completed_at marker can tell them apart. Flagging it would regenerate
    hours of already-published audio.
    """
    _make_book(tmp_path, 7, 11, 11)
    chapter = _chapter(tmp_path, 7, 11)
    _make_chunks(chapter, 456, 0)
    assert pending_work.interrupted_stage(chapter) is None


def test_interrupted_stage_ignores_undownloaded_chapter(tmp_path):
    _make_book(tmp_path, 7, 11, 10)
    assert pending_work.interrupted_stage(_chapter(tmp_path, 7, 11)) is None


def test_select_pending_interrupted_generation(tmp_path):
    """Source is caught up and every chapter is normalized, but one died mid-TTS."""
    _make_book(tmp_path, 7, 11, 11)
    chapter = _chapter(tmp_path, 7, 11)
    (chapter / "metadata.json").unlink()
    _make_chunks(chapter, 456, 205)
    assert pending_work.select_pending({7: 11}, tmp_path, floor=7) == [7]


def test_select_pending_ignores_pruned_completed_book(tmp_path):
    _make_book(tmp_path, 7, 11, 11)
    for i in range(1, 12):
        _make_chunks(_chapter(tmp_path, 7, i), 20, 0)
    assert pending_work.select_pending({7: 11}, tmp_path, floor=7) == []


def test_list_interrupted_reports_progress_in_chapter_order(tmp_path):
    _make_book(tmp_path, 7, 11, 11)
    for number, texts, wavs in ((2, 456, 205), (10, 0, 0)):
        chapter = _chapter(tmp_path, 7, number)
        (chapter / "metadata.json").unlink()
        _make_chunks(chapter, texts, wavs)
    chapters_dir = tmp_path / "book_7" / "chapters"
    assert pending_work.list_interrupted(chapters_dir) == [
        (2, "generate", 205, 456),
        (10, "chunk", 0, 0),
    ]
