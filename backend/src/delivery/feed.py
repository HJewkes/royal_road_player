"""Podcast RSS feed generation for delivering exported chapters to a phone.

Scans the exports directory, groups chapter mp3s into series, and builds one
podcast RSS feed per series. Each chapter is an <item> with an <enclosure>
pointing at its object URL under the configured public base. A podcast app
(Overcast) subscribes to the feed once and then auto-downloads new chapters and
notifies — no per-chapter taps, and immune to the Mac sleeping because the files
live in always-on object storage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

# exports/<Series Title> - Book <n>/... - Chapter <c>.mp3
_BOOK_DIR_RE = re.compile(r"^(?P<series>.+?)\s*-\s*Book\s+(?P<book>\d+)\s*$", re.IGNORECASE)
_CHAPTER_FILE_RE = re.compile(r"Chapter\s+(?P<chapter>\d+)\.mp3$", re.IGNORECASE)


def slugify(name: str) -> str:
    """Lowercase, hyphen-separated, URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "series"


def object_key_for(series_slug: str, book: int, chapter: int) -> str:
    """Stable R2 object key for a chapter mp3. Used by both feed and uploader."""
    return f"{series_slug}/book-{book:02d}/chapter-{chapter:03d}.mp3"


def feed_key_for(series_slug: str) -> str:
    """Stable R2 object key for a series' feed.xml."""
    return f"{series_slug}/feed.xml"


def prefixed(key: str, prefix: str = "") -> str:
    """Prepend the unguessable delivery prefix to a relative object key."""
    prefix = prefix.strip("/")
    return f"{prefix}/{key}" if prefix else key


@dataclass(frozen=True)
class Episode:
    series: str
    series_slug: str
    book: int
    chapter: int
    path: Path
    size: int
    mtime: float

    @property
    def object_key(self) -> str:
        return object_key_for(self.series_slug, self.book, self.chapter)

    @property
    def title(self) -> str:
        return f"Book {self.book}, Chapter {self.chapter}"

    @property
    def short_series(self) -> str:
        """Series name without its subtitle — "Soccer Supremo", not the full
        "Soccer Supremo - A Sports Progression Fantasy", which is too long to
        read on a phone once it's prefixed to every episode title."""
        return self.series.split(" - ", 1)[0].strip()

    @property
    def qualified_title(self) -> str:
        """Title for a feed spanning several series, where "Book 7" is ambiguous."""
        return f"{self.short_series} — {self.title}"

    @property
    def guid(self) -> str:
        return self.object_key


def discover_episodes(exports_dir: Path) -> dict[str, list[Episode]]:
    """Group all exported chapter mp3s by series slug, each sorted by (book, chapter)."""
    series: dict[str, list[Episode]] = {}
    if not exports_dir.is_dir():
        return series

    for book_dir in sorted(exports_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        m = _BOOK_DIR_RE.match(book_dir.name)
        if not m:
            continue
        name = m.group("series").strip()
        book = int(m.group("book"))
        slug = slugify(name)
        for mp3 in book_dir.glob("*.mp3"):
            cm = _CHAPTER_FILE_RE.search(mp3.name)
            if not cm:
                continue
            st = mp3.stat()
            series.setdefault(slug, []).append(Episode(
                series=name,
                series_slug=slug,
                book=book,
                chapter=int(cm.group("chapter")),
                path=mp3,
                size=st.st_size,
                mtime=st.st_mtime,
            ))

    for eps in series.values():
        eps.sort(key=lambda e: (e.book, e.chapter))
    return series


def _monotonic_dates(episodes: list[Episode]) -> list[datetime]:
    """One pubDate per episode, strictly increasing in (book, chapter) order.

    Anchored on each file's real mtime so a freshly exported chapter gets a
    near-now pubDate (which is what makes the podcast app treat it as new and
    notify), while clustered historical mtimes are nudged apart by a second so
    playback order is always correct.
    """
    dates: list[datetime] = []
    prev: datetime | None = None
    for ep in episodes:
        dt = datetime.fromtimestamp(ep.mtime, tz=timezone.utc)
        if prev is not None and dt <= prev:
            dt = prev + timedelta(seconds=1)
        prev = dt
        dates.append(dt)
    return dates


def _seasons_for(episodes: list[Episode], span_series: bool) -> list[int]:
    """One iTunes season number per episode.

    Within a single series the book number is the season. A collection feed
    spans several series whose book numbers overlap (Player Manager 7 and
    Soccer Supremo 7 both exist), so each distinct (series, book) instead gets
    the next season number in reading order.
    """
    if not span_series:
        return [ep.book for ep in episodes]

    seasons: dict[tuple[str, int], int] = {}
    for ep in episodes:
        seasons.setdefault((ep.series_slug, ep.book), len(seasons) + 1)
    return [seasons[(ep.series_slug, ep.book)] for ep in episodes]


def build_feed(
    series_name: str,
    episodes: list[Episode],
    base_url: str,
    author: str = "Audiobook Pipeline",
    prefix: str = "",
    feed_slug: str | None = None,
    span_series: bool = False,
) -> str:
    """Render a podcast RSS 2.0 feed for a series — or, when span_series is set,
    for a collection of series presented as one continuous story.

    feed_slug overrides where the feed's self-link points, which lets a
    collection feed be published at an existing series' key so a phone that
    already subscribed there keeps working without re-subscribing.
    """
    base = base_url.rstrip("/")
    slug = feed_slug or slugify(series_name)
    feed_url = f"{base}/{prefixed(feed_key_for(slug), prefix)}"
    dates = _monotonic_dates(episodes)
    seasons = _seasons_for(episodes, span_series)

    items = []
    for ep, dt, season in zip(episodes, dates, seasons):
        url = f"{base}/{prefixed(ep.object_key, prefix)}"
        title = ep.qualified_title if span_series else ep.title
        items.append(
            "    <item>\n"
            f"      <title>{escape(title)}</title>\n"
            f"      <guid isPermaLink=\"false\">{escape(ep.guid)}</guid>\n"
            f"      <pubDate>{format_datetime(dt)}</pubDate>\n"
            f"      <enclosure url={quoteattr(url)} length=\"{ep.size}\" type=\"audio/mpeg\"/>\n"
            f"      <itunes:title>{escape(title)}</itunes:title>\n"
            f"      <itunes:season>{season}</itunes:season>\n"
            f"      <itunes:episode>{ep.chapter}</itunes:episode>\n"
            f"      <itunes:order>{ep.chapter}</itunes:order>\n"
            "    </item>"
        )

    channel_date = format_datetime(dates[-1]) if dates else format_datetime(
        datetime(2000, 1, 1, tzinfo=timezone.utc)
    )
    items_xml = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape(series_name)}</title>\n"
        f"    <link>{escape(base)}</link>\n"
        f"    <atom:link href={quoteattr(feed_url)} rel=\"self\" type=\"application/rss+xml\"/>\n"
        "    <language>en-us</language>\n"
        f"    <description>{escape(series_name)} — audiobook chapters</description>\n"
        f"    <itunes:author>{escape(author)}</itunes:author>\n"
        '    <itunes:type>serial</itunes:type>\n'
        f"    <lastBuildDate>{channel_date}</lastBuildDate>\n"
        f"{items_xml}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def collection_episodes(
    exports_dir: Path, series_slugs: list[str]
) -> list[Episode]:
    """Every episode of the named series, in reading order.

    Series order follows series_slugs (the story's chronology, which no
    filesystem ordering recovers); within a series, (book, chapter). Slugs with
    nothing exported yet are skipped, so a not-yet-started series can be listed
    ahead of time.
    """
    by_series = discover_episodes(exports_dir)
    ordered: list[Episode] = []
    for slug in series_slugs:
        ordered.extend(by_series.get(slug, []))
    return ordered


def build_collection_feed(
    exports_dir: Path,
    title: str,
    series_slugs: list[str],
    base_url: str,
    author: str = "Audiobook Pipeline",
    prefix: str = "",
    feed_slug: str | None = None,
) -> str | None:
    """Render one feed spanning several series. None when nothing is exported."""
    episodes = collection_episodes(exports_dir, series_slugs)
    if not episodes:
        return None
    return build_feed(
        title, episodes, base_url, author, prefix,
        feed_slug=feed_slug or slugify(title), span_series=True,
    )


def build_all_feeds(
    exports_dir: Path,
    base_url: str,
    author: str = "Audiobook Pipeline",
    prefix: str = "",
) -> dict[str, str]:
    """Return {series_slug: feed_xml} for every series found in exports."""
    feeds: dict[str, str] = {}
    for slug, episodes in discover_episodes(exports_dir).items():
        if episodes:
            feeds[slug] = build_feed(episodes[0].series, episodes, base_url, author, prefix)
    return feeds
