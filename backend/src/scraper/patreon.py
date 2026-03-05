"""Patreon scraper for downloading chapters from Patreon creator feeds."""

import json
import logging
import re
import time
from datetime import datetime
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

from src.config import get_settings
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

    def _fetch_all_posts(self, campaign_id: str) -> list[dict]:
        """Fetch all posts for a campaign using cursor-based pagination."""
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
            all_posts.extend(posts)

            # Cursor pagination
            next_link = data.get("links", {}).get("next")
            if next_link:
                url = next_link
                params = None  # Next link includes all params
            else:
                break

            logger.debug(f"Fetched {len(all_posts)} posts so far...")

        logger.info(f"Fetched {len(all_posts)} total posts for campaign {campaign_id}")
        return all_posts

    def _parse_chapter_title(self, title: str) -> tuple[int, int, str] | None:
        """Parse a post title into (book_number, chapter_number, clean_title).

        Returns None if the title doesn't match the chapter pattern.
        """
        match = self._chapter_pattern.match(title.strip())
        if not match:
            return None

        book_num = int(match.group(1))
        chapter_num = int(match.group(2))
        clean_title = match.group(3).strip()
        return book_num, chapter_num, clean_title

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
        campaign_id = fiction_id.removeprefix("patreon_")

        # If it's not numeric, treat as slug and resolve
        if not campaign_id.isdigit():
            campaign_id = self._resolve_campaign_id(campaign_id)

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
        self, fiction_id: str, book_number: Optional[int] = None
    ) -> list[dict]:
        """Get list of chapters from Patreon posts.

        Returns list of dicts with: url, number, title, book_number
        """
        campaign_id = fiction_id.removeprefix("patreon_")
        if not campaign_id.isdigit():
            campaign_id = self._resolve_campaign_id(campaign_id)

        posts = self._fetch_all_posts(campaign_id)
        chapters = self._filter_chapter_posts(posts, book_number)

        # Renumber sequentially within the book (1-based)
        result = []
        for i, ch in enumerate(chapters, 1):
            result.append({
                "url": ch["post_id"],  # Post ID used as chapter ref
                "number": i,
                "title": ch["title"],
                "book_number": ch["book_number"],
                "chapter_number": ch["chapter_number"],
            })

        return result

    def get_books_from_posts(self, fiction_id: str) -> list[dict]:
        """Derive book list from post titles (Patreon-specific, not in Protocol)."""
        campaign_id = fiction_id.removeprefix("patreon_")
        if not campaign_id.isdigit():
            campaign_id = self._resolve_campaign_id(campaign_id)

        posts = self._fetch_all_posts(campaign_id)
        chapters = self._filter_chapter_posts(posts)

        books: dict[int, int] = {}
        for ch in chapters:
            book_num = ch["book_number"]
            books[book_num] = books.get(book_num, 0) + 1

        return sorted([
            {"book_number": num, "chapter_count": count}
            for num, count in books.items()
        ], key=lambda b: b["book_number"])

    def download_chapter_text(self, chapter_ref: str) -> str:
        """Download and extract text from a Patreon post.

        Args:
            chapter_ref: Post ID
        """
        data = self._fetch_api(
            f"{self.BASE_URL}/api/posts/{chapter_ref}",
            params={"fields[post]": "content,title"},
        )

        content = data.get("data", {}).get("attributes", {}).get("content", "")
        if not content:
            raise ValueError(f"Post {chapter_ref} has no content")

        return self._html_to_text(content)

    def download_book(
        self,
        fiction_id: str,
        book_number: int,
        delay: float = 1.0,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> BookMetadata:
        """Download a complete book from Patreon posts."""
        info = self.get_fiction_info(fiction_id)
        title = info["title"]

        logger.info(f"Downloading: {title} - Book {book_number}")
        if on_progress:
            on_progress(0, f"Starting download: {title}")

        metadata = BookMetadata(
            fiction_id=fiction_id,
            book_number=book_number,
            title=f"{title} - Book {book_number}",
            author=info["author"],
            source_url=info["url"],
            scraped_at=datetime.utcnow(),
        )

        book = self.book_discovery.create_book(metadata)

        chapters = self.get_chapter_list(fiction_id, book_number)
        logger.info(f"Found {len(chapters)} chapters")
        if on_progress:
            on_progress(0, f"Found {len(chapters)} chapters")

        metadata.chapter_count = len(chapters)

        for i, chapter_info in enumerate(chapters, 1):
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
