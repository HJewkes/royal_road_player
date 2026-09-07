"""Tests for persisted author-commentary removals.

Covers the pure reapply function that /api/normalize calls, and the applier
autopull hands the Claude decisions to. The point of the whole mechanism is that
a decision survives a re-chunk, where every chunk filename changes, so the tests
work in text rather than filenames wherever they can.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from src.api.routes import strip_recorded_commentary
from src.text.chunker import TextChunker
from src.text.commentary import (
    apply_recorded_removals,
    commentary_path,
    load_records,
    save_records,
)

_APPLIER = Path(__file__).resolve().parents[2] / "scripts" / "apply_commentary.py"
_spec = importlib.util.spec_from_file_location("apply_commentary", _APPLIER)
apply_commentary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_commentary)

STORY = 'He nodded.\n\n"Top top top. I\'ll drive."'
TAIL = "\n\n…\n\nThanks for your support!"


def _record(kind, text):
    return {"kind": kind, "text": text}


def test_removes_a_recorded_trailing_span():
    cleaned, missing = apply_recorded_removals(STORY + TAIL, [_record("trailing", TAIL)])
    assert cleaned == STORY + "\n"
    assert missing == []


def test_reports_a_record_it_cannot_find_and_leaves_the_text_alone():
    cleaned, missing = apply_recorded_removals(STORY, [_record("trailing", TAIL)])
    assert cleaned == STORY
    assert missing == [TAIL]


def test_applies_every_record():
    text = "Thanks for reading!\n\n" + STORY + TAIL
    cleaned, missing = apply_recorded_removals(
        text, [_record("preamble", "Thanks for reading!\n\n"), _record("trailing", TAIL)]
    )
    assert cleaned == STORY + "\n"
    assert missing == []


def test_running_twice_changes_nothing_the_second_time():
    records = [_record("trailing", TAIL)]
    once, _ = apply_recorded_removals(STORY + TAIL, records)
    twice, missing = apply_recorded_removals(once, records)
    assert twice == once
    assert missing == [TAIL]


def test_trailing_span_is_matched_from_the_end():
    # The marker text also appears mid-story; only the closing one is commentary.
    text = f"…{STORY}{TAIL}"
    cleaned, _ = apply_recorded_removals(text, [_record("trailing", TAIL)])
    assert cleaned == f"…{STORY}\n"


def test_records_round_trip_through_disk(tmp_path):
    save_records(tmp_path, [_record("trailing", TAIL)])
    assert load_records(tmp_path) == [_record("trailing", TAIL)]
    assert json.loads(commentary_path(tmp_path).read_text())["version"] == 1


def test_no_record_on_disk_means_no_removals(tmp_path):
    assert load_records(tmp_path) == []
    assert apply_recorded_removals(STORY, load_records(tmp_path)) == (STORY, [])


def test_unreadable_record_is_ignored(tmp_path):
    commentary_path(tmp_path).write_text("{not json")
    assert load_records(tmp_path) == []


def test_normalize_hook_strips_recorded_commentary(tmp_path):
    save_records(tmp_path, [_record("trailing", TAIL)])
    assert strip_recorded_commentary(STORY + TAIL, tmp_path) == STORY + "\n"


# --- the applier autopull calls ------------------------------------------


def _chapter(tmp_path: Path, text: str) -> Path:
    """A chapter dir whose chunks come from text, exactly as /api/chunk builds them."""
    chunks = tmp_path / "chunks"
    chunks.mkdir(parents=True)
    (tmp_path / "normalized.txt").write_text(text)
    for chunk in TextChunker().chunk(text):
        (chunks / f"{chunk.index:03d}.txt").write_text(chunk.text)
        (chunks / f"{chunk.index:03d}.wav").write_bytes(b"RIFF")
    return tmp_path


def _chunk_texts(chapter: Path) -> list[str]:
    files = sorted(chapter.glob("chunks/*.txt"), key=lambda p: int(p.stem))
    return [p.read_text() for p in files]


def test_applier_cleans_normalized_text_so_a_rechunk_stays_clean(tmp_path):
    chapter = _chapter(tmp_path, STORY + TAIL)
    last = _chunk_texts(chapter)[-1]
    decisions = {
        "delete_chunks": [f"{len(_chunk_texts(chapter)):03d}.txt"],
        "strip_trailing": {"file": "002.txt", "remove_from": "…"},
    }

    apply_commentary.apply_commentary(chapter, "[]", json.dumps(decisions))

    assert last == "Thanks for your support!"
    cleaned = (chapter / "normalized.txt").read_text()
    assert "Thanks for your support!" not in cleaned
    rechunked = "".join(c.text for c in TextChunker().chunk(cleaned))
    assert "Thanks for your support!" not in rechunked


def test_applier_records_the_removed_text_not_the_filenames(tmp_path):
    chapter = _chapter(tmp_path, STORY + TAIL)
    decisions = {"delete_chunks": ["003.txt"], "strip_trailing": {"file": "002.txt", "remove_from": "…"}}

    apply_commentary.apply_commentary(chapter, "[]", json.dumps(decisions))

    assert load_records(chapter) == [_record("trailing", TAIL)]


def test_applier_deletes_the_wav_of_a_stripped_chunk_so_it_regenerates(tmp_path):
    chapter = _chapter(tmp_path, STORY + TAIL)
    decisions = {"delete_chunks": ["003.txt"], "strip_trailing": {"file": "002.txt", "remove_from": "…"}}

    apply_commentary.apply_commentary(chapter, "[]", json.dumps(decisions))

    assert not (chapter / "chunks/002.wav").exists()
    assert not (chapter / "chunks/003.txt").exists()
    assert not (chapter / "chunks/003.wav").exists()


def test_applier_records_a_deleted_preamble_chunk(tmp_path):
    chapter = _chapter(tmp_path, "Thanks for your support!\n\n" + STORY)

    apply_commentary.apply_commentary(chapter, json.dumps(["001.txt"]), "{}")

    assert load_records(chapter) == [_record("preamble", "Thanks for your support!")]
    assert (chapter / "normalized.txt").read_text() == STORY + "\n"


@pytest.mark.parametrize("preamble, commentary", [("[]", "{}"), ("garbage", "garbage")])
def test_applier_writes_nothing_when_there_is_nothing_to_remove(tmp_path, preamble, commentary):
    chapter = _chapter(tmp_path, STORY)
    before = _chunk_texts(chapter)

    apply_commentary.apply_commentary(chapter, preamble, commentary)

    assert not commentary_path(chapter).exists()
    assert _chunk_texts(chapter) == before


def test_applier_records_scattered_deletions_one_by_one(tmp_path):
    """Deletions that don't run to the end of the chapter aren't a trailing span,
    so each chunk is recorded on its own rather than swallowing the story between."""
    chapter = _chapter(tmp_path, STORY + TAIL)

    apply_commentary.apply_commentary(chapter, "[]", json.dumps({"delete_chunks": ["001.txt"]}))

    assert load_records(chapter) == [_record("chunk", "He nodded.")]
