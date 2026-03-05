"""Royal Road scraper for downloading books and chapters."""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.config import get_settings
from src.discovery import BookDiscovery, ChapterDiscovery
from src.models import BookMetadata, ChapterMetadata
from src.utils import sanitize_filename, retry_http

logger = logging.getLogger(__name__)


class RoyalRoadScraper:
    """Scraper for Royal Road web fiction."""

    BASE_URL = "https://www.royalroad.com"

    def __init__(self):
        """Initialize the scraper."""
        self.settings = get_settings()
        self.book_discovery = BookDiscovery()
        self.chapter_discovery = ChapterDiscovery()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/2.0)"
        })

    @retry_http(max_retries=3, base_delay=1.0)
    def _fetch(self, url: str) -> BeautifulSoup:
        """
        Fetch and parse a URL with automatic retry on transient errors.
        
        Uses exponential backoff with jitter to handle:
        - Connection errors
        - Timeout errors
        - 429 (rate limit), 5xx server errors
        """
        logger.debug(f"Fetching: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.content, "lxml")

    def _sanitize_filename(self, name: str, max_length: int = 100) -> str:
        """Make a string safe for filesystem use."""
        return sanitize_filename(name, max_length)

    def get_fiction_info(self, fiction_id: str) -> dict:
        """
        Get fiction metadata from Royal Road.

        Args:
            fiction_id: Fiction ID (just the number, e.g., "58187")

        Returns:
            Dictionary with title, author, url
        """
        url = f"{self.BASE_URL}/fiction/{fiction_id}"
        soup = self._fetch(url)

        # Extract title
        title_elem = soup.find("h1") or soup.find("title")
        title = title_elem.get_text(strip=True) if title_elem else "Unknown"
        title = re.sub(r'\s*\|\s*Royal Road.*$', '', title)

        # Extract author
        author_elem = soup.find("a", href=re.compile(r"/profile/"))
        author = author_elem.get_text(strip=True) if author_elem else None

        return {
            "fiction_id": fiction_id,
            "title": title,
            "author": author,
            "url": url,
        }

    def get_all_books_in_series(self, fiction_id: str) -> list[dict]:
        """
        Detect all books in a series by scanning chapter names.

        Args:
            fiction_id: Fiction ID

        Returns:
            List of book info dicts with book_number and chapter_count
        """
        url = f"{self.BASE_URL}/fiction/{fiction_id}"
        soup = self._fetch(url)

        books: dict[int, int] = {}  # book_number -> chapter_count
        chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")

        for link in soup.find_all("a", href=chapter_pattern):
            link_text = link.get_text().lower().strip()

            # Skip timestamp links
            if re.match(r'^\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', link_text):
                continue

            # Try to extract book number from chapter title (e.g., "7.1", "11.5")
            book_match = re.match(r'^(\d+)\.\d+', link_text)
            if book_match:
                book_num = int(book_match.group(1))
                books[book_num] = books.get(book_num, 0) + 1
                continue

            # Try URL pattern (e.g., "/book-7/")
            href = link.get("href", "")
            url_book_match = re.search(r"/book-(\d+)", href, re.I)
            if url_book_match:
                book_num = int(url_book_match.group(1))
                books[book_num] = books.get(book_num, 0) + 1

        # Convert to list sorted by book number
        result = [
            {"book_number": num, "chapter_count": count}
            for num, count in sorted(books.items())
        ]

        return result

    def get_chapter_list(
        self,
        fiction_id: str,
        book_number: Optional[int] = None,
    ) -> list[dict]:
        """
        Get list of chapters for a fiction.

        Args:
            fiction_id: Fiction ID
            book_number: Optional book number to filter

        Returns:
            List of chapter dictionaries with url, number, title
        """
        url = f"{self.BASE_URL}/fiction/{fiction_id}"
        soup = self._fetch(url)

        chapters = []
        chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")

        for link in soup.find_all("a", href=chapter_pattern):
            href = link.get("href", "")
            if not href:
                continue

            link_text = link.get_text().lower().strip()

            # Skip timestamp links
            if re.match(r'^\d+\s*(second|minute|hour|day|week|month|year)s?\s*ago', link_text):
                continue

            # Filter by book number
            if book_number:
                # Check URL for book-X pattern
                book_match = re.search(r"/book-(\d+)", href, re.I)
                if book_match and int(book_match.group(1)) != book_number:
                    continue

                # Check chapter numbering (e.g., "7.1" for book 7)
                chapter_num_match = re.search(r"^(\d+)\.", link_text)
                if chapter_num_match:
                    if int(chapter_num_match.group(1)) != book_number:
                        continue
                elif not re.match(r'^(chapter|\d)', link_text, re.I):
                    # Skip non-matching links when filtering
                    continue

            full_url = urljoin(self.BASE_URL, href)
            chapter_match = re.search(r"/chapter/(\d+)", href)
            chapter_num = int(chapter_match.group(1)) if chapter_match else len(chapters) + 1
            title = link.get_text(strip=True) or f"Chapter {chapter_num}"

            chapters.append({
                "url": full_url,
                "number": chapter_num,
                "title": title,
            })

        # Remove duplicates and sort
        seen = set()
        unique = []
        for ch in chapters:
            if ch["number"] not in seen:
                seen.add(ch["number"])
                unique.append(ch)

        return sorted(unique, key=lambda x: x["number"])

    def download_chapter_text(self, chapter_url: str) -> str:
        """
        Download and extract text from a chapter.

        Args:
            chapter_url: Full URL to the chapter

        Returns:
            Chapter text content
        """
        soup = self._fetch(chapter_url)

        # Find chapter content div
        content_div = (
            soup.find("div", class_=lambda x: x and "chapter-content" in str(x).lower())
            or soup.find("div", class_=lambda x: x and "chapter" in str(x).lower())
        )

        if not content_div:
            raise ValueError("Could not find chapter content")

        # Extract text with paragraph preservation
        text = self._html_to_text(content_div)

        return text

    def _html_to_text(self, element) -> str:
        """Convert HTML element to plain text with paragraph preservation."""
        lines = []

        for elem in element.descendants:
            if isinstance(elem, str):
                text = elem.strip()
                if text:
                    lines.append(text)
            elif elem.name in ('p', 'br', 'div'):
                lines.append('\n')

        # Join and normalize
        text = ' '.join(lines)
        text = re.sub(r'\s*\n\s*', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def download_book(
        self,
        fiction_id: str,
        book_number: int,
        delay: float = 1.0,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> BookMetadata:
        """
        Download a complete book with all chapters.

        Args:
            fiction_id: Fiction ID
            book_number: Book number within the fiction
            delay: Delay between chapter downloads (seconds)
            on_progress: Optional callback for progress updates (chapters_done, message)

        Returns:
            BookMetadata for the downloaded book
        """
        # Get fiction info
        info = self.get_fiction_info(fiction_id)
        title = info["title"]

        logger.info(f"Downloading: {title} - Book {book_number}")
        if on_progress:
            on_progress(0, f"Starting download: {title}")

        # Create book metadata
        metadata = BookMetadata(
            fiction_id=fiction_id,
            book_number=book_number,
            title=f"{title} - Book {book_number}",
            author=info["author"],
            source_url=info["url"],
            scraped_at=datetime.utcnow(),
        )

        # Create book
        book = self.book_discovery.create_book(metadata)

        # Get chapters
        chapters = self.get_chapter_list(fiction_id, book_number)
        logger.info(f"Found {len(chapters)} chapters")
        if on_progress:
            on_progress(0, f"Found {len(chapters)} chapters")

        metadata.chapter_count = len(chapters)

        # Download each chapter
        for i, chapter_info in enumerate(chapters, 1):
            logger.info(f"Downloading chapter {i}/{len(chapters)}: {chapter_info['title']}")
            if on_progress:
                on_progress(i - 1, f"Downloading chapter {i}/{len(chapters)}: {chapter_info['title']}")

            try:
                text = self.download_chapter_text(chapter_info["url"])

                # Create chapter metadata
                chapter_meta = ChapterMetadata(
                    chapter_number=i,
                    title=chapter_info["title"],
                    source_url=chapter_info["url"],
                    scraped_at=datetime.utcnow(),
                )

                # Save chapter
                self.chapter_discovery.create_chapter(
                    fiction_id, book_number, chapter_meta
                )
                self.chapter_discovery.save_raw_text(
                    fiction_id, book_number, i, text
                )

                logger.info(f"✅ Saved chapter {i} ({len(text)} chars)")
                if on_progress:
                    on_progress(i, f"Downloaded chapter {i}/{len(chapters)}")

                # Rate limiting
                if i < len(chapters):
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Failed to download chapter {i}: {e}")
                raise

        # Update book metadata with chapter count
        book_path = self.book_discovery.get_book_path(fiction_id, book_number)
        with open(book_path / "metadata.json", "w") as f:
            json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"✅ Downloaded book: {metadata.title}")
        return metadata


# Convenience function
def get_scraper() -> RoyalRoadScraper:
    """Get scraper instance."""
    return RoyalRoadScraper()

