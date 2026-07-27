"""Tests for Patreon chapter-title parsing and series-tag book offsets.

The author renamed the story mid-run and restarted numbering at 1.1 under a
"DoF" tag. Those posts must land as book 8 of the existing local sequence so
they keep flowing into the same collection and podcast feed instead of
colliding with book 1 (and sitting below autopull's discovery floor).

No network or auth: the scraper's parsing surface is exercised directly.
"""
import re

import pytest

from src.config import Settings
from src.scraper.patreon import PatreonScraper


@pytest.fixture
def scraper():
    """A PatreonScraper wired for parsing only — no session cookie needed."""
    parser = PatreonScraper.__new__(PatreonScraper)
    settings = Settings()
    parser._chapter_pattern = re.compile(settings.patreon_chapter_pattern)
    parser._series = dict(settings.patreon_series)
    return parser


@pytest.mark.parametrize("title,expected", [
    ("7.16 - Appendix [T3]", (7, 16, "Appendix")),
    ("7.9 - The Plot Thickens [T2]", (7, 9, "The Plot Thickens")),
    ("1.1 - Wales, Golf, Madrid", (1, 1, "Wales, Golf, Madrid")),
])
def test_untagged_titles_keep_their_own_numbering(scraper, title, expected):
    assert scraper._parse_chapter_title(title) == expected


@pytest.mark.parametrize("title,expected", [
    ("DoF 1.1 - Celebrity Escape to the Country [T3]",
     (8, 1, "Celebrity Escape to the Country")),
    ("DoF 1.12 - Compartmental", (8, 12, "Compartmental")),
    ("DoF 2.1 - Second Book", (9, 1, "Second Book")),
])
def test_tagged_titles_continue_the_local_book_sequence(scraper, title, expected):
    assert scraper._parse_chapter_title(title) == expected


@pytest.mark.parametrize("title", [
    "SS7 Bonus: Player Wanderer",
    "Book 6 Bonus 1: Writer's Ramble",
    "Soccer Supremo 1 Audiobook",
    "Chapter Tomorrow",
    "Bonus: Never Walk Alone",
])
def test_non_chapter_posts_are_ignored(scraper, title):
    assert scraper._parse_chapter_title(title) is None


def test_unmapped_tag_is_parsed_but_warned(scraper, caplog):
    """A future rename still parses; the warning is the only pickup signal."""
    assert scraper._parse_chapter_title("XYZ 2.3 - Something") == (2, 3, "Something")
    assert "Unmapped series tag" in caplog.text


def test_offset_shifts_the_whole_book(scraper):
    """Every chapter of a tagged book lands in the same shifted book."""
    books = {
        scraper._parse_chapter_title(f"DoF 1.{n} - Chapter {n}")[0]
        for n in range(1, 20)
    }
    assert books == {8}


@pytest.mark.parametrize("local_book,expected_title", [
    (1, None),
    (7, None),
    (8, "DoF"),
    (12, "DoF"),
])
def test_series_ownership_of_local_book_numbers(scraper, local_book, expected_title):
    """Books above a series' offset belong to it; earlier ones predate the rename."""
    owner = scraper._series_for_book(local_book)
    assert (owner.title if owner else None) == expected_title


def test_renamed_series_book_is_displayed_with_its_own_numbering(scraper):
    """Local book 8 is published as "DoF - Book 1" — storage and display differ."""
    series = scraper._series_for_book(8)
    assert f"{series.title} - Book {8 - series.offset}" == "DoF - Book 1"


def test_later_rename_takes_over_from_the_earlier_one(scraper):
    """Ownership follows the highest offset below the book, not the first match."""
    from src.config import PatreonSeries

    scraper._series = {
        "DoF": PatreonSeries(offset=7, title="DoF"),
        "NXT": PatreonSeries(offset=10, title="Next Thing"),
    }
    assert scraper._series_for_book(9).title == "DoF"
    assert scraper._series_for_book(11).title == "Next Thing"
