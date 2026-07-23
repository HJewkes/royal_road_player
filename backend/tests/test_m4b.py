"""Tests for the m4b audiobook packaging helpers (pure logic, no ffmpeg)."""

import importlib.util
from pathlib import Path

import pytest

from src.export import m4b


def test_default_titles():
    assert m4b.default_titles(3) == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert m4b.default_titles(0) == []


def test_parse_titles_ignores_comments_and_blanks():
    text = "# header\n\nTitle\n  Chapter 1 - A  \n# note\nCredits\n"
    assert m4b.parse_titles_text(text, 3) == ["Title", "Chapter 1 - A", "Credits"]


def test_parse_titles_count_mismatch_raises():
    with pytest.raises(ValueError):
        m4b.parse_titles_text("One\nTwo\n", 3)


def test_escape_meta_handles_special_chars():
    assert m4b._escape_meta("a=b;c#d\\e") == "a\\=b\\;c\\#d\\\\e"


def test_build_ffmetadata_cumulative_and_structure():
    meta = m4b.build_ffmetadata(
        [1000, 2000, 500],
        ["Intro", "Chapter 1", "Outro"],
        title="Book", author="Me",
    )
    assert meta.startswith(";FFMETADATA1")
    assert "media_type=2" in meta
    assert "album=Book" in meta  # album defaults to title
    # 3 chapters, cumulative offsets 0 -> 1000 -> 3000 -> 3500
    assert meta.count("[CHAPTER]") == 3
    assert "START=0\nEND=1000" in meta
    assert "START=1000\nEND=3000" in meta
    assert "START=3000\nEND=3500" in meta
    assert "title=Outro" in meta


def test_build_ffmetadata_length_mismatch_raises():
    with pytest.raises(ValueError):
        m4b.build_ffmetadata([1000], ["a", "b"], title="B", author="A")


def test_build_ffmetadata_escapes_titles():
    meta = m4b.build_ffmetadata(
        [1000], ["Waiting for God? Oh; = #x"], title="B", author="A")
    assert "title=Waiting for God? Oh\\; \\= \\#x" in meta


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "mp3s_to_m4b", Path(__file__).resolve().parents[2] / "scripts" / "mp3s_to_m4b.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_propose_title_extracts_chapter_and_name():
    cli = _load_cli()
    heard = "Chapter 9 FC Hollywood Part 1. A fumed and scoured pretty much all the way"
    assert cli._propose_title(heard) == "Chapter 9 - FC Hollywood Part 1"


def test_propose_title_falls_back_to_first_clause():
    cli = _load_cli()
    heard = "The story so far. Max Best was a call centre drone living in Manchester"
    assert cli._propose_title(heard) == "The story so far"


def test_fmt_ts():
    cli = _load_cli()
    assert cli._fmt_ts(9700) == "0:09"
    assert cli._fmt_ts(135800) == "2:15"
