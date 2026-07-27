"""Tests for podcast feed generation."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import re

import pytest

from src.delivery.feed import (
    build_all_feeds,
    build_collection_feed,
    build_feed,
    collection_episodes,
    discover_episodes,
    object_key_for,
    slugify,
)

BASE = "https://pub-xxxx.r2.dev/ab-secret"


def _make_exports(tmp: Path, layout: dict[str, list[int]]) -> Path:
    """layout: {"<Series> - Book N": [chapter, ...]} -> writes dummy mp3s."""
    exports = tmp / "exports"
    for folder, chapters in layout.items():
        d = exports / folder
        d.mkdir(parents=True)
        for ch in chapters:
            (d / f"{folder} - Chapter {ch}.mp3").write_bytes(b"x" * (1000 + ch))
    return exports


def test_slug_and_key():
    assert slugify("Test Series - A Grand Tale") == "test-series-a-grand-tale"
    assert object_key_for("my-series", 7, 15) == "my-series/book-07/chapter-015.mp3"


def test_discover_groups_by_series_and_sorts(tmp_path):
    exports = _make_exports(tmp_path, {
        "Test Series - Book 7": [10, 2, 1],
        "Test Series - Book 6": [14],
        "Demo Books - Book 1": [1],
    })
    series = discover_episodes(exports)

    assert set(series) == {"test-series", "demo-books"}
    eps = series["test-series"]
    # sorted by (book, chapter): b6c14, b7c1, b7c2, b7c10
    assert [(e.book, e.chapter) for e in eps] == [(6, 14), (7, 1), (7, 2), (7, 10)]


def test_discover_ignores_non_chapter_files_and_stray_dirs(tmp_path):
    exports = _make_exports(tmp_path, {"Test Series - Book 7": [1]})
    (exports / "Test Series - Book 7" / "cover.jpg").write_bytes(b"img")
    (exports / "not-a-book-folder").mkdir()
    series = discover_episodes(exports)
    assert len(series["test-series"]) == 1


def test_build_feed_has_enclosures_and_valid_urls(tmp_path):
    exports = _make_exports(tmp_path, {"Test Series - Book 7": [1, 2]})
    eps = discover_episodes(exports)["test-series"]
    xml = build_feed("Test Series", eps, BASE)

    assert xml.startswith("<?xml")
    assert xml.count("<item>") == 2
    assert f'url="{BASE}/test-series/book-07/chapter-001.mp3"' in xml
    assert f'url="{BASE}/test-series/book-07/chapter-002.mp3"' in xml
    # enclosure length must be the real byte size
    assert 'length="1001"' in xml and 'length="1002"' in xml


def test_pubdates_are_strictly_increasing_in_order(tmp_path):
    """Even with identical mtimes, playback order must be preserved."""
    exports = _make_exports(tmp_path, {"Test Series - Book 7": [1, 2, 3]})
    d = exports / "Test Series - Book 7"
    same = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    for mp3 in d.glob("*.mp3"):
        import os
        os.utime(mp3, (same, same))

    eps = discover_episodes(exports)["test-series"]
    xml = build_feed("Test Series", eps, BASE)
    dates = [parsedate_to_datetime(m) for m in re.findall(r"<pubDate>(.*?)</pubDate>", xml)]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)  # all distinct


def test_newest_chapter_gets_recent_pubdate_for_notification(tmp_path):
    """A freshly exported chapter must carry a near-now pubDate so the podcast
    app treats it as new and notifies."""
    exports = _make_exports(tmp_path, {"Test Series - Book 7": [1, 2]})
    eps = discover_episodes(exports)["test-series"]  # real mtimes ~ now
    xml = build_feed("Test Series", eps, BASE)
    dates = [parsedate_to_datetime(m) for m in re.findall(r"<pubDate>(.*?)</pubDate>", xml)]
    newest = max(dates)
    age = datetime.now(timezone.utc) - newest
    assert age.total_seconds() < 300


def test_xml_escapes_special_characters(tmp_path):
    exports = _make_exports(tmp_path, {"Ben & Co <Test> - Book 1": [1]})
    eps = discover_episodes(exports)["ben-co-test"]
    xml = build_feed("Ben & Co <Test>", eps, BASE)
    assert "Ben &amp; Co &lt;Test&gt;" in xml
    assert "<Test>" not in xml.replace("&lt;Test&gt;", "")


def test_secret_prefix_applied_to_feed_and_enclosure_urls(tmp_path):
    exports = _make_exports(tmp_path, {"Test Series - Book 7": [1]})
    eps = discover_episodes(exports)["test-series"]
    xml = build_feed("Test Series", eps, BASE, prefix="ab-s3cr3t")

    # both the mp3 enclosure and the feed self-link live under the secret prefix
    assert f'url="{BASE}/ab-s3cr3t/test-series/book-07/chapter-001.mp3"' in xml
    assert f'href="{BASE}/ab-s3cr3t/test-series/feed.xml"' in xml
    # guid stays the stable relative key (not prefixed) so it never churns
    assert "<guid isPermaLink=\"false\">test-series/book-07/chapter-001.mp3</guid>" in xml


def _make_universe(tmp_path: Path) -> Path:
    """Three series that are really one story, exported out of reading order."""
    return _make_exports(tmp_path, {
        "Second Series - Book 1": [1, 2],
        "Second Series - Book 2": [1],
        "First Series - Book 4": [1],
        "DoF - Book 1": [1],
    })


UNIVERSE = ["first-series", "second-series", "dof"]


def test_collection_orders_series_then_book_then_chapter(tmp_path):
    """Reading order comes from the configured series list, not the filesystem."""
    eps = collection_episodes(_make_universe(tmp_path), UNIVERSE)
    assert [(e.series_slug, e.book, e.chapter) for e in eps] == [
        ("first-series", 4, 1),
        ("second-series", 1, 1),
        ("second-series", 1, 2),
        ("second-series", 2, 1),
        ("dof", 1, 1),
    ]


def test_collection_skips_series_with_nothing_exported(tmp_path):
    """A series can be listed before its first chapter exists."""
    exports = _make_exports(tmp_path, {"First Series - Book 4": [1]})
    eps = collection_episodes(exports, [*UNIVERSE, "not-started-yet"])
    assert [e.series_slug for e in eps] == ["first-series"]


def test_collection_qualifies_titles_and_renumbers_seasons(tmp_path):
    """Book numbers repeat across series, so seasons run over the whole story."""
    xml = build_collection_feed(_make_universe(tmp_path), "Max Best Universe",
                                UNIVERSE, BASE)
    assert "<title>Max Best Universe</title>" in xml
    assert "<title>DoF — Book 1, Chapter 1</title>" in xml
    assert "<title>First Series — Book 4, Chapter 1</title>" in xml
    # 4 distinct (series, book) pairs -> seasons 1..4, DoF last
    seasons = re.findall(r"<itunes:season>(\d+)</itunes:season>", xml)
    assert seasons == ["1", "2", "2", "3", "4"]


def test_collection_keeps_per_series_guids_and_object_keys(tmp_path):
    """Grouping must not churn guids, or every episode re-downloads."""
    xml = build_collection_feed(_make_universe(tmp_path), "Max Best Universe",
                                UNIVERSE, BASE)
    assert '<guid isPermaLink="false">dof/book-01/chapter-001.mp3</guid>' in xml
    assert f'url="{BASE}/second-series/book-02/chapter-001.mp3"' in xml
    assert "max-best-universe/book" not in xml


def test_collection_feed_can_be_published_at_an_existing_series_key(tmp_path):
    """Serving the collection at an old subscription's URL avoids re-subscribing."""
    xml = build_collection_feed(_make_universe(tmp_path), "Max Best Universe",
                                UNIVERSE, BASE, feed_slug="second-series")
    assert f'href="{BASE}/second-series/feed.xml"' in xml


def test_collection_newest_chapter_stays_newest(tmp_path):
    """The last episode in reading order must still carry a near-now pubDate."""
    xml = build_collection_feed(_make_universe(tmp_path), "Max Best Universe",
                                UNIVERSE, BASE)
    dates = [parsedate_to_datetime(m) for m in re.findall(r"<pubDate>(.*?)</pubDate>", xml)]
    assert dates == sorted(dates)
    assert (datetime.now(timezone.utc) - dates[-1]).total_seconds() < 300


def test_collection_item_titles_drop_the_series_subtitle(tmp_path):
    """"Soccer Supremo — Book 7, Chapter 1", not the full shelf title."""
    exports = _make_exports(tmp_path, {
        "Soccer Supremo - A Sports Progression Fantasy - Book 7": [1],
    })
    xml = build_collection_feed(exports, "Max Best Universe",
                                ["soccer-supremo-a-sports-progression-fantasy"], BASE)
    assert "<title>Soccer Supremo — Book 7, Chapter 1</title>" in xml


def test_collection_feed_is_none_when_nothing_exported(tmp_path):
    assert build_collection_feed(tmp_path / "exports", "Max Best Universe",
                                 UNIVERSE, BASE) is None


def test_build_all_feeds_one_per_series(tmp_path):
    exports = _make_exports(tmp_path, {
        "Test Series - Book 7": [1],
        "Demo Books - Book 1": [1],
    })
    feeds = build_all_feeds(exports, BASE)
    assert set(feeds) == {"test-series", "demo-books"}
    assert all(x.startswith("<?xml") for x in feeds.values())
