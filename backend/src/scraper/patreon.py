"""Patreon scraper for downloading chapters from Patreon creator feeds."""

import json
import logging
import re
import time
from datetime import datetime
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

from src.config import PatreonSeries, get_settings
from src.discovery import BookDiscovery, ChapterDiscovery
from src.models import BookMetadata, ChapterMetadata
from src.utils import retry_http

logger = logging.getLogger(__name__)


class PatreonScraper:
    """Scraper for Patreon creator feeds using session cookie auth."""

    BASE_URL = "https://www.patreon.com"

    def __init__(self):
        self.settings = get_settings()
        self.book_discovery = BookDiscovery()
        self.chapter_discovery = ChapterDiscovery()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/2.0)",
        })
        self._set_auth_cookie()
        self._chapter_pattern = re.compile(self.settings.patreon_chapter_pattern)
        self._series = dict(self.settings.patreon_series)

    def _set_auth_cookie(self):
        """Set session cookie for authenticated requests."""
        session_id = self.settings.patreon_session_id
        if not session_id:
            raise ValueError(
                "AUDIOBOOK_PATREON_SESSION_ID not set. "
                "Copy session_id cookie from browser DevTools."
            )
        self.session.cookies.set("session_id", session_id, domain=".patreon.com")

    def _resolve_campaign_id(self, creator_slug: str) -> str:
        """Resolve a creator slug to a campaign ID by fetching the creator page."""
        url = f"{self.BASE_URL}/c/{creator_slug}/posts"
        logger.debug(f"Resolving campaign ID from: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        # Campaign ID is embedded in the page HTML/JSON
        match = re.search(r'"campaign_id"\s*:\s*(\d+)', response.text)
        if not match:
            # Try alternative pattern
            match = re.search(r'"id"\s*:\s*"(\d+)"[^}]*"type"\s*:\s*"campaign"', response.text)
        if not match:
            raise ValueError(f"Could not find campaign_id for creator '{creator_slug}'")

        campaign_id = match.group(1)
        logger.info(f"Resolved campaign ID for '{creator_slug}': {campaign_id}")
        return campaign_id

    @retry_http(max_retries=3, base_delay=1.0)
    def _fetch_api(self, url: str, params: dict | None = None) -> dict:
        """Fetch JSON from Patreon's internal API with retry."""
        logger.debug(f"Fetching API: {url}")
        response = self.session.get(url, params=params, timeout=30)

        if response.status_code in (401, 403):
            raise PermissionError(
                "Patreon session expired or invalid. "
                "Update AUDIOBOOK_PATREON_SESSION_ID with a fresh cookie."
            )

        response.raise_for_status()
        return response.json()

    def _fetch_all_posts(self, campaign_id: str, months_back: int = 4) -> list[dict]:
        """Fetch recent posts for a campaign using cursor-based pagination.

        Args:
            campaign_id: Patreon campaign ID
            months_back: Only fetch posts from the last N months (default 2)
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=months_back * 30)
        cutoff_iso = cutoff.isoformat() + "Z"

        all_posts = []
        url = f"{self.BASE_URL}/api/posts"
        params = {
            "filter[campaign_id]": campaign_id,
            "filter[is_by_creator]": "true",
            "sort": "-published_at",
            "json-api-use-default-includes": "false",
            "fields[post]": "title,content,published_at,url",
        }

        while url:
            data = self._fetch_api(url, params=params)
            posts = data.get("data", [])

            # Posts are sorted newest-first; stop when we hit the cutoff
            hit_cutoff = False
            for post in posts:
                published = post.get("attributes", {}).get("published_at", "")
                if published and published < cutoff_iso:
                    hit_cutoff = True
                    break
                all_posts.append(post)

            if hit_cutoff:
                break

            next_link = data.get("links", {}).get("next")
            if next_link:
                url = next_link
                params = None
            else:
                break

            logger.debug(f"Fetched {len(all_posts)} posts so far...")

        logger.info(f"Fetched {len(all_posts)} posts (last {months_back} months) for campaign {campaign_id}")
        return all_posts

    def _parse_chapter_title(self, title: str) -> tuple[int, int, str] | None:
        """Parse a post title into (book_number, chapter_number, clean_title).

        A leading series tag ("DoF 1.1 - ...") shifts the book number by that
        tag's configured offset so a renamed, renumbered series continues the
        local book sequence instead of colliding with book 1.

        Returns None if the title doesn't match the chapter pattern.
        """
        match = self._chapter_pattern.match(title.strip())
        if not match:
            return None

        parts = match.groupdict()
        series_tag = parts.get("series")
        series = self._series.get(series_tag) if series_tag else None
        if series_tag and series is None:
            # An unmapped tag lands on the author's own book 1, which sits below
            # autopull's discovery floor and would silently never be picked up.
            logger.warning(
                "Unmapped series tag %r in post title %r — add it to "
                "AUDIOBOOK_PATREON_SERIES or its chapters will be skipped",
                series_tag, title,
            )
        book_num = int(parts["book"]) + (series.offset if series else 0)
        chapter_num = int(parts["chapter"])
        clean_title = parts["title"].strip()
        return book_num, chapter_num, clean_title

    def _series_for_book(self, book_number: int) -> PatreonSeries | None:
        """The configured series that owns a local book number, if any.

        Each series owns every local book above its offset, up to the next
        (higher-offset) series. Books at or below the lowest offset predate any
        rename and keep the fiction's own title.
        """
        owner = None
        for series in self._series.values():
            if book_number > series.offset and (
                owner is None or series.offset > owner.offset
            ):
                owner = series
        return owner

    def _filter_chapter_posts(
        self, posts: list[dict], book_number: int | None = None
    ) -> list[dict]:
        """Filter posts to chapter posts, optionally for a specific book."""
        chapters = []
        for post in posts:
            attrs = post.get("attributes", {})
            title = attrs.get("title", "")
            parsed = self._parse_chapter_title(title)
            if not parsed:
                continue

            book_num, chapter_num, clean_title = parsed
            if book_number is not None and book_num != book_number:
                continue

            chapters.append({
                "post_id": post["id"],
                "book_number": book_num,
                "chapter_number": chapter_num,
                "title": clean_title,
                "published_at": attrs.get("published_at", ""),
                "url": attrs.get("url", ""),
            })

        # Sort by book number, then chapter number
        chapters.sort(key=lambda c: (c["book_number"], c["chapter_number"]))
        return chapters

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text with paragraph preservation."""
        soup = BeautifulSoup(html_content, "lxml")
        lines = []

        for elem in soup.descendants:
            if isinstance(elem, str):
                text = elem.strip()
                if text:
                    lines.append(text)
            elif elem.name in ('p', 'br', 'div'):
                lines.append('\n')

        text = ' '.join(lines)
        text = re.sub(r'\s*\n\s*', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def get_fiction_info(self, fiction_id: str) -> dict:
        """Get fiction metadata from Patreon.

        Args:
            fiction_id: Patreon fiction ID in format "patreon_<campaign_id>"
                        or "patreon_<creator_slug>"
        """
        campaign_id = self._resolve_campaign_id_from_fiction(fiction_id)

        url = f"{self.BASE_URL}/api/campaigns/{campaign_id}"
        try:
            data = self._fetch_api(url)
            attrs = data.get("data", {}).get("attributes", {})
            creator_name = attrs.get("creator_name", attrs.get("name", "Unknown"))
            title = attrs.get("creation_name", creator_name)
        except Exception:
            # Fallback: use posts to get basic info
            posts = self._fetch_all_posts(campaign_id)
            chapter_posts = self._filter_chapter_posts(posts)
            title = "Soccer Supremo" if chapter_posts else "Unknown"
            creator_name = None

        return {
            "fiction_id": fiction_id,
            "title": title,
            "author": creator_name,
            "url": f"{self.BASE_URL}/c/{campaign_id}",
            "campaign_id": campaign_id,
        }

    def get_chapter_list(
        self,
        fiction_id: str,
        book_number: Optional[int] = None,
        series_index: int | None = None,
    ) -> list[dict]:
        """Get list of chapters from Patreon posts.

        Args:
            fiction_id: Patreon fiction ID
            book_number: Filter to a specific book number
            series_index: Filter to a specific series (0-based). Required when
                         multiple series have overlapping book numbers.

        Returns list of dicts with: url, number, title, book_number
        """
        campaign_id = self._resolve_campaign_id_from_fiction(fiction_id)

        posts = self._fetch_all_posts(campaign_id)
        all_chapters = self._filter_chapter_posts(posts)

        # If series_index specified, filter to that series' chapters
        if series_index is not None:
            series_list = self._detect_series_from_posts(all_chapters)
            if 0 <= series_index < len(series_list):
                # Get the post_ids belonging to this series
                sorted_chapters = sorted(all_chapters, key=lambda c: c["published_at"])
                series_boundaries = []
                max_book = 0
                current_start = 0
                for j, ch in enumerate(sorted_chapters):
                    if ch["book_number"] <= max_book and ch["book_number"] == 1 and j > 0:
                        series_boundaries.append((current_start, j))
                        current_start = j
                        max_book = 0
                    max_book = max(max_book, ch["book_number"])
                series_boundaries.append((current_start, len(sorted_chapters)))

                if series_index < len(series_boundaries):
                    start, end = series_boundaries[series_index]
                    series_post_ids = {ch["post_id"] for ch in sorted_chapters[start:end]}
                    all_chapters = [ch for ch in all_chapters if ch["post_id"] in series_post_ids]

        # Filter by book number
        if book_number is not None:
            all_chapters = [ch for ch in all_chapters if ch["book_number"] == book_number]

        # Sort by book number, then chapter number
        all_chapters.sort(key=lambda c: (c["book_number"], c["chapter_number"]))

        # Renumber sequentially within the book (1-based)
        result = []
        for i, ch in enumerate(all_chapters, 1):
            result.append({
                "url": ch["post_id"],
                "number": i,
                "title": ch["title"],
                "book_number": ch["book_number"],
                "chapter_number": ch["chapter_number"],
            })

        return result

    def _detect_series_from_posts(self, chapters: list[dict]) -> list[dict]:
        """Detect multiple series by finding where book numbers restart.

        When book numbers go backwards (e.g., Book 4 followed by Book 1),
        that signals a new series. Returns a list of series, each with
        a name, date range, and book list.
        """
        if not chapters:
            return []

        # Sort by publication date (oldest first)
        sorted_chapters = sorted(chapters, key=lambda c: c["published_at"])

        series_list: list[list[dict]] = [[]]
        max_book_in_current_series = 0

        for ch in sorted_chapters:
            book_num = ch["book_number"]
            if book_num <= max_book_in_current_series and book_num == 1:
                # Book numbers restarted — new series
                series_list.append([])
                max_book_in_current_series = 0
            max_book_in_current_series = max(max_book_in_current_series, book_num)
            series_list[-1].append(ch)

        # Build series info
        default_names = ["Player Manager", "Soccer Supremo"]
        result = []
        for i, series_chapters in enumerate(series_list):
            if not series_chapters:
                continue

            # Group by book number
            books: dict[int, list[dict]] = {}
            for ch in series_chapters:
                books.setdefault(ch["book_number"], []).append(ch)

            dates = [ch["published_at"] for ch in series_chapters if ch["published_at"]]
            first_date = min(dates) if dates else ""
            last_date = max(dates) if dates else ""

            name = default_names[i] if i < len(default_names) else f"Series {i + 1}"

            book_list = sorted([
                {
                    "book_number": num,
                    "chapter_count": len(chs),
                    "first_date": min(c["published_at"] for c in chs) if chs else "",
                    "last_date": max(c["published_at"] for c in chs) if chs else "",
                }
                for num, chs in books.items()
            ], key=lambda b: b["book_number"])

            result.append({
                "series_index": i,
                "name": name,
                "first_date": first_date[:10] if first_date else "",
                "last_date": last_date[:10] if last_date else "",
                "book_count": len(books),
                "chapter_count": len(series_chapters),
                "books": book_list,
            })

        return result

    def get_books_from_posts(self, fiction_id: str, series_index: int | None = None) -> list[dict]:
        """Derive book list from post titles (Patreon-specific, not in Protocol).

        Args:
            fiction_id: Patreon fiction ID
            series_index: If set, only return books from this series (0-based).
                         If None, returns all books (legacy behavior).
        """
        campaign_id = self._resolve_campaign_id_from_fiction(fiction_id)
        posts = self._fetch_all_posts(campaign_id)
        chapters = self._filter_chapter_posts(posts)

        if series_index is not None:
            series_list = self._detect_series_from_posts(chapters)
            if 0 <= series_index < len(series_list):
                return series_list[series_index]["books"]
            return []

        books: dict[int, int] = {}
        for ch in chapters:
            book_num = ch["book_number"]
            books[book_num] = books.get(book_num, 0) + 1

        return sorted([
            {"book_number": num, "chapter_count": count}
            for num, count in books.items()
        ], key=lambda b: b["book_number"])

    def get_series_preview(self, fiction_id: str) -> list[dict]:
        """Get a preview of all detected series with their books and date ranges."""
        campaign_id = self._resolve_campaign_id_from_fiction(fiction_id)
        posts = self._fetch_all_posts(campaign_id)
        chapters = self._filter_chapter_posts(posts)
        return self._detect_series_from_posts(chapters)

    def _resolve_series_title(
        self, fiction_id: str, source_fid: str, series_index: int | None
    ) -> str | None:
        """Resolve the series title by checking existing local book metadata.

        Strips the "- Book N" suffix from an existing book's title so the
        Patreon books match the Royal Road naming convention.
        """
        existing = self.book_discovery.list_books(fiction_id)
        for book in existing:
            if book.title:
                # Strip "- Book N" suffix to get base title
                base = re.sub(r'\s*-\s*Book\s+\d+\s*$', '', book.title)
                if base and base != book.title:
                    return base

        # Fall back to series detection name
        if series_index is not None:
            campaign_id = self._resolve_campaign_id_from_fiction(source_fid)
            posts = self._fetch_all_posts(campaign_id)
            chapters = self._filter_chapter_posts(posts)
            series_list = self._detect_series_from_posts(chapters)
            if 0 <= series_index < len(series_list):
                return series_list[series_index]["name"]

        return None

    def _extract_series_index(self, fiction_id: str) -> int | None:
        """Extract series index from fiction_id like patreon_tedsteel_s1."""
        m = re.search(r'_s(\d+)$', fiction_id)
        return int(m.group(1)) if m else None

    def _resolve_campaign_id_from_fiction(self, fiction_id: str) -> str:
        """Extract campaign ID from fiction_id, resolving slug if needed.

        Handles formats like: patreon_9319026, patreon_tedsteel, patreon_tedsteel_s1
        """
        stripped = fiction_id.removeprefix("patreon_")
        # Remove series suffix like _s0, _s1
        stripped = re.sub(r'_s\d+$', '', stripped)
        if not stripped.isdigit():
            stripped = self._resolve_campaign_id(stripped)
        return stripped

    def _prosemirror_to_text(self, doc: dict) -> str:
        """Convert ProseMirror JSON document to plain text."""
        lines = []

        def walk(node: dict):
            node_type = node.get("type", "")
            if node_type == "text":
                lines.append(node.get("text", ""))
            elif node_type in ("paragraph", "heading"):
                for child in node.get("content", []):
                    walk(child)
                lines.append("\n\n")
            elif node_type == "hardBreak":
                lines.append("\n")
            else:
                for child in node.get("content", []):
                    walk(child)

        walk(doc)
        text = "".join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def download_chapter_text(self, chapter_ref: str) -> str:
        """Download and extract text from a Patreon post.

        Args:
            chapter_ref: Post ID
        """
        data = self._fetch_api(
            f"{self.BASE_URL}/api/posts/{chapter_ref}",
            params={"fields[post]": "content,content_json_string,title"},
        )

        attrs = data.get("data", {}).get("attributes", {})

        # Try content_json_string first (ProseMirror JSON)
        json_str = attrs.get("content_json_string")
        if json_str:
            doc = json.loads(json_str)
            text = self._prosemirror_to_text(doc)
            if text:
                return text

        # Fallback to HTML content
        content = attrs.get("content", "")
        if content:
            return self._html_to_text(content)

        raise ValueError(f"Post {chapter_ref} has no content")

    def download_book(
        self,
        fiction_id: str,
        book_number: int,
        delay: float = 1.0,
        on_progress: Optional[Callable[[int, str], None]] = None,
        fetch_fiction_id: str | None = None,
    ) -> BookMetadata:
        """Download a complete book from Patreon posts.

        Args:
            fiction_id: Local fiction ID for saving files (e.g., "58187")
            fetch_fiction_id: Patreon fiction ID for API calls (e.g., "patreon_tedsteel").
                            If None, uses fiction_id for both.
        """
        source_fid = fetch_fiction_id or fiction_id
        info = self.get_fiction_info(source_fid)

        series_index = self._extract_series_index(source_fid)

        # A renamed continuation is published under its own title and its own
        # restarted book number ("DoF - Book 1"), even though it is stored at the
        # shifted local book number that keeps the data layout monotonic.
        # Everything before the rename derives its title from existing local
        # books (matches RR naming), falling back to series name then campaign.
        series = self._series_for_book(book_number)
        if series:
            title = series.title
            display_book = book_number - series.offset
        else:
            title = self._resolve_series_title(
                fiction_id, source_fid, series_index
            ) or info["title"]
            display_book = book_number

        logger.info(f"Downloading: {title} - Book {display_book} (local book {book_number})")
        if on_progress:
            on_progress(0, f"Starting download: {title}")

        metadata = BookMetadata(
            fiction_id=fiction_id,
            book_number=book_number,
            title=f"{title} - Book {display_book}",
            author=info["author"],
            source_url=info["url"],
            scraped_at=datetime.utcnow(),
        )

        book = self.book_discovery.create_book(metadata)
        chapters = self.get_chapter_list(source_fid, book_number, series_index=series_index)
        logger.info(f"Found {len(chapters)} chapters")
        if on_progress:
            on_progress(0, f"Found {len(chapters)} chapters")

        metadata.chapter_count = len(chapters)

        for i, chapter_info in enumerate(chapters, 1):
            # Skip chapters that already have raw text
            existing_text = self.chapter_discovery.get_raw_text(
                fiction_id, book_number, i
            )
            if existing_text:
                logger.info(f"Skipping chapter {i}/{len(chapters)} (already downloaded)")
                if on_progress:
                    on_progress(i, f"Skipped chapter {i}/{len(chapters)} (exists)")
                continue

            logger.info(f"Downloading chapter {i}/{len(chapters)}: {chapter_info['title']}")
            if on_progress:
                on_progress(i - 1, f"Downloading chapter {i}/{len(chapters)}: {chapter_info['title']}")

            try:
                text = self.download_chapter_text(chapter_info["url"])

                chapter_meta = ChapterMetadata(
                    chapter_number=i,
                    title=chapter_info["title"],
                    source_url=f"{self.BASE_URL}/api/posts/{chapter_info['url']}",
                    scraped_at=datetime.utcnow(),
                )

                self.chapter_discovery.create_chapter(
                    fiction_id, book_number, chapter_meta
                )
                self.chapter_discovery.save_raw_text(
                    fiction_id, book_number, i, text
                )

                logger.info(f"Saved chapter {i} ({len(text)} chars)")
                if on_progress:
                    on_progress(i, f"Downloaded chapter {i}/{len(chapters)}")

                if i < len(chapters):
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Failed to download chapter {i}: {e}")
                raise

        book_path = self.book_discovery.get_book_path(fiction_id, book_number)
        with open(book_path / "metadata.json", "w") as f:
            json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Downloaded book: {metadata.title}")
        return metadata
