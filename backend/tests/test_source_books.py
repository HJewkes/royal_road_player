"""Tests for the autopull source-discovery helper (scripts/source_books.py).

Covers the patreon_meta.json bridging that lets a numeric (Royal-Road-style)
fiction_id resolve to its real Patreon campaign — the crux of autopull's
new-book discovery. Network-touching code (the scraper) is not exercised here.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_HELPER = Path(__file__).resolve().parents[2] / "scripts" / "source_books.py"
_spec = importlib.util.spec_from_file_location("source_books", _HELPER)
source_books = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source_books)


@pytest.mark.parametrize("url,expected", [
    ("https://www.patreon.com/c/tedsteel/posts", "patreon_tedsteel"),
    ("https://www.patreon.com/c/9319026", "patreon_9319026"),
    ("https://www.royalroad.com/fiction/124774", None),
    ("", None),
])
def test_parse_patreon_fid(url, expected):
    assert source_books._parse_patreon_fid(url) == expected


def test_resolve_patreon_prefixed_id_passes_through(tmp_path):
    assert source_books.resolve_source("patreon_tedsteel", tmp_path) == (
        "patreon", "patreon_tedsteel",
    )


def test_resolve_bridges_numeric_id_via_meta(tmp_path):
    """A numeric fiction_id with patreon_meta.json resolves to its campaign."""
    fiction_dir = tmp_path / "124774"
    fiction_dir.mkdir()
    (fiction_dir / "patreon_meta.json").write_text(json.dumps({
        "source": "patreon",
        "patreon_url": "https://www.patreon.com/c/tedsteel/posts",
    }))
    assert source_books.resolve_source("124774", tmp_path) == (
        "patreon", "patreon_tedsteel",
    )


def test_resolve_numeric_id_without_meta_is_royal_road(tmp_path):
    assert source_books.resolve_source("124774", tmp_path) == (
        "royal_road", "124774",
    )


def test_resolve_unparseable_meta_falls_back_to_royal_road(tmp_path):
    fiction_dir = tmp_path / "124774"
    fiction_dir.mkdir()
    (fiction_dir / "patreon_meta.json").write_text(json.dumps({"source": "patreon"}))
    assert source_books.resolve_source("124774", tmp_path) == (
        "royal_road", "124774",
    )
