"""Royal Road chapter scraper."""

import json
import re
import signal
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.scraper.formatter import TextFormatter
from src.utils.config import get_settings
from src.utils.filename import sanitize_filename, sanitize_chapter_filename
from src.utils.metrics import MetricsCollector
from src.utils.metadata_tracker import MetadataTracker


class RoyalRoadScraper:
    """Scraper for Royal Road chapters."""

    def __init__(self):
        """Initialize scraper with settings."""
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.scraper_user_agent})
        self.formatter = TextFormatter()
        self.metrics = MetricsCollector()
        self._should_stop = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully."""
        print("\n⚠️  Interrupt received. Stopping gracefully...")
        self._should_stop = True
        sys.exit(130)  # Standard exit code for SIGINT

    def _extract_book_id(self, url: str) -> str:
        """
        Extract book ID from Royal Road URL.

        Args:
            url: Royal Road book or chapter URL

        Returns:
            Book ID string
        """
        # Royal Road URLs: https://www.royalroad.com/fiction/{id}/title
        # or https://www.royalroad.com/fiction/{id}/title/chapter/{chapter_num}/title
        match = re.search(r"/fiction/(\d+)", url)
        if match:
            return f"book_{match.group(1)}"
        raise ValueError(f"Could not extract book ID from URL: {url}")

    def _get_book_title(self, book_url: str) -> str:
        """
        Extract book title from Royal Road page.

        Args:
            book_url: URL to the Royal Road book page

        Returns:
            Book title string
        """
        try:
            response = self.session.get(book_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            # Try to find the book title
            # Royal Road typically has it in an h1 or in the page title
            title_elem = (
                soup.find("h1", class_=lambda x: x and "fiction" in str(x).lower())
                or soup.find("h1")
                or soup.find("title")
            )

            if title_elem:
                title = title_elem.get_text(strip=True)
                # Remove " | Royal Road" suffix if present
                title = re.sub(r'\s*\|\s*Royal Road.*$', '', title, flags=re.I)
                return title

            # Fallback: extract from URL slug
            match = re.search(r'/fiction/\d+/([^/]+)', book_url)
            if match:
                slug = match.group(1)
                # Convert slug to title (replace hyphens with spaces, title case)
                title = slug.replace('-', ' ').title()
                return title

            return "Unknown Book"

        except Exception:
            # Fallback to ID-based name
            return None

    def _get_all_chapters(self, book_url: str) -> list[dict]:
        """
        Get ALL chapters from book page (no filtering).

        Args:
            book_url: URL to the Royal Road book page

        Returns:
            List of all chapter dictionaries with url, number, and title
        """
        try:
            # Try table of contents page first
            toc_url = book_url.rstrip("/") + "/table-of-contents"
            response = self.session.get(toc_url, timeout=30)
            
            # If TOC doesn't exist, fall back to main page
            if response.status_code != 200:
                response = self.session.get(book_url, timeout=30)
            
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            chapters = []
            # Royal Road chapter links - handle both formats:
            # /fiction/ID/title/chapter/NUM/title
            # /fiction/ID/title/chapter/NUM/book-X
            chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")
            chapter_links = soup.find_all("a", href=chapter_pattern)

            for link in chapter_links:
                href = link.get("href", "")
                if not href:
                    continue

                full_url = urljoin("https://www.royalroad.com", href)
                
                # Extract chapter number from URL
                chapter_match = re.search(r"/chapter/(\d+)", href)
                chapter_num = int(chapter_match.group(1)) if chapter_match else len(chapters) + 1
                title = link.get_text(strip=True) or f"Chapter {chapter_num}"

                chapters.append({
                    "url": full_url,
                    "number": chapter_num,
                    "title": title,
                })

            # Remove duplicates (same chapter number)
            seen_numbers = set()
            unique_chapters = []
            for chapter in chapters:
                if chapter["number"] not in seen_numbers:
                    seen_numbers.add(chapter["number"])
                    unique_chapters.append(chapter)

            # Sort by chapter number
            unique_chapters.sort(key=lambda x: x["number"])
            return unique_chapters

        except Exception as e:
            raise RuntimeError(f"Failed to get chapter list: {e}") from e

    def _filter_chapters_by_book(self, chapters: list[dict], book_number: int) -> list[dict]:
        """
        Filter chapters to only include those from a specific book number.

        Args:
            chapters: List of chapter dictionaries
            book_number: Book number to filter by (e.g., 7)

        Returns:
            Filtered list of chapters
        """
        filtered = []
        for chapter in chapters:
            title = chapter["title"]
            url = chapter.get("url", "")
            
            # Check chapter numbering pattern (e.g., "7.1", "7.2" - must start with book number)
            chapter_num_match = re.search(r"^(\d+)\.", title)
            if chapter_num_match:
                chapter_book_num = int(chapter_num_match.group(1))
                if chapter_book_num == book_number:
                    filtered.append(chapter)
                    continue
            
            # Check URL for book-X pattern
            book_match = re.search(r"/book-(\d+)", url, re.I)
            if book_match:
                url_book_num = int(book_match.group(1))
                if url_book_num == book_number:
                    filtered.append(chapter)
                    continue
            
            # Check text for explicit book mention
            title_lower = title.lower()
            if f"book {book_number}" in title_lower or f"book-{book_number}" in title_lower:
                filtered.append(chapter)
                continue
        
        return filtered

    def _get_chapter_list(self, book_url: str, filter_book_number: Optional[int] = None) -> list[dict]:
        """
        Get list of chapter URLs from book page.

        Args:
            book_url: URL to the Royal Road book page
            filter_book_number: Optional book number to filter chapters (e.g., 7 for Book 7)

        Returns:
            List of chapter dictionaries with url, number, and title
        """
        try:
            # Try table of contents page first
            toc_url = book_url.rstrip("/") + "/table-of-contents"
            response = self.session.get(toc_url, timeout=30)
            
            # If TOC doesn't exist, fall back to main page
            if response.status_code != 200:
                response = self.session.get(book_url, timeout=30)
            
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            chapters = []
            # Royal Road chapter links - handle both formats:
            # /fiction/ID/title/chapter/NUM/title
            # /fiction/ID/title/chapter/NUM/book-X
            chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")
            chapter_links = soup.find_all("a", href=chapter_pattern)

            for link in chapter_links:
                href = link.get("href", "")
                if not href:
                    continue

                # Filter by book number if specified
                if filter_book_number:
                    # Check if URL contains book-X pattern
                    book_match = re.search(r"/book-(\d+)", href, re.I)
                    if book_match:
                        book_num = int(book_match.group(1))
                        if book_num != filter_book_number:
                            continue
                    # Also check title text for book number
                    link_text = link.get_text().lower()
                    if f"book {filter_book_number}" not in link_text and f"book-{filter_book_number}" not in link_text:
                        # Check if it's clearly from a different book
                        other_book_match = re.search(r"book\s*(\d+)", link_text)
                        if other_book_match and int(other_book_match.group(1)) != filter_book_number:
                            continue

                full_url = urljoin("https://www.royalroad.com", href)
                
                # Extract chapter number from URL
                chapter_match = re.search(r"/chapter/(\d+)", href)
                chapter_num = int(chapter_match.group(1)) if chapter_match else len(chapters) + 1
                title = link.get_text(strip=True) or f"Chapter {chapter_num}"

                chapters.append({
                    "url": full_url,
                    "number": chapter_num,
                    "title": title,
                })

            # Remove duplicates (same chapter number)
            seen_numbers = set()
            unique_chapters = []
            for chapter in chapters:
                if chapter["number"] not in seen_numbers:
                    seen_numbers.add(chapter["number"])
                    unique_chapters.append(chapter)

            # Sort by chapter number
            unique_chapters.sort(key=lambda x: x["number"])
            return unique_chapters

        except Exception as e:
            raise RuntimeError(f"Failed to get chapter list: {e}") from e

    def scrape_chapter(self, chapter_url: str, chapter_number: Optional[int] = None) -> dict:
        """
        Scrape a single chapter.

        Args:
            chapter_url: URL to the chapter page
            chapter_number: Optional chapter number for logging

        Returns:
            Dictionary with chapter content and metadata

        Raises:
            requests.RequestException: If download fails
        """
        try:
            response = self.session.get(chapter_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            # Find the main chapter content
            # Royal Road chapters are typically in a div with class containing "chapter-content"
            content_div = (
                soup.find("div", class_=re.compile(r"chapter.*content", re.I))
                or soup.find("div", id=re.compile(r"chapter.*content", re.I))
                or soup.find("div", class_="chapter-content")
            )

            if not content_div:
                # Fallback: look for the largest div with text content
                divs = soup.find_all("div")
                content_div = max(divs, key=lambda d: len(d.get_text()))

            # Extract title
            title_elem = (
                soup.find("h1", class_=re.compile(r"chapter.*title", re.I))
                or soup.find("h1")
                or soup.find("h2", class_=re.compile(r"chapter.*title", re.I))
            )
            title = title_elem.get_text(strip=True) if title_elem else f"Chapter {chapter_number or 'Unknown'}"

            # Get HTML content
            html_content = str(content_div)

            # Convert to Markdown to preserve formatting (tables, lists, etc.)
            text = self.formatter.html_to_text(html_content, output_format="markdown")
            text = self.formatter.clean_text(text)

            # Calculate text quality (ratio of non-whitespace to total)
            total_chars = len(text)
            clean_chars = len(text.replace("\n", "").replace(" ", ""))
            quality_ratio = (clean_chars / total_chars * 100) if total_chars > 0 else 0.0

            self.metrics.record_text_quality(quality_ratio)

            return {
                "title": title,
                "content": text,
                "html_content": html_content,
                "word_count": len(text.split()),
                "quality_ratio": quality_ratio,
            }

        except requests.RequestException as e:
            error_msg = f"HTTP error: {e}"
            self.metrics.record_chapter_download(
                success=False, error=error_msg, chapter_number=chapter_number
            )
            raise
        except Exception as e:
            error_msg = f"Parsing error: {e}"
            self.metrics.record_chapter_download(
                success=False, error=error_msg, chapter_number=chapter_number
            )
            raise RuntimeError(f"Failed to scrape chapter: {e}") from e

    def scrape_book(
        self,
        book_url: str,
        output_dir: Optional[Path] = None,
        max_chapters: Optional[int] = None,
        filter_book_number: Optional[int] = None,
    ) -> dict:
        """
        Scrape all chapters from a Royal Road book.

        Args:
            book_url: URL to the Royal Road book page
            output_dir: Directory to save chapters (defaults to data/books/{book_id})
            max_chapters: Optional limit on number of chapters to scrape

        Returns:
            Dictionary with book metadata and chapter information
        """
        self.metrics.start()

        try:
            book_id = self._extract_book_id(book_url)
            
            # Get book title for better directory naming
            book_title = self._get_book_title(book_url)
            if book_title:
                # Sanitize title for filesystem
                safe_title = sanitize_filename(book_title)
                # Add book number suffix if filtering
                if filter_book_number:
                    safe_title = f"{safe_title} - Book {filter_book_number}"
                # Combine with ID for uniqueness
                dir_name = f"{safe_title} ({book_id})"
            else:
                dir_name = book_id
                if filter_book_number:
                    dir_name = f"{book_id}_book_{filter_book_number}"

            if output_dir is None:
                output_dir = self.settings.books_dir / dir_name

            # Create directory structure
            chapters_dir = output_dir / "chapters"
            chapters_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Get ALL chapters first
            print(f"📚 Fetching all chapters for {book_id}...")
            all_chapters = self._get_all_chapters(book_url)
            print(f"📖 Found {len(all_chapters)} total chapters")

            # Step 2: Filter by book number if specified
            if filter_book_number:
                print(f"🔍 Filtering for Book {filter_book_number}...")
                chapter_list = self._filter_chapters_by_book(all_chapters, filter_book_number)
                print(f"✅ Found {len(chapter_list)} chapters in Book {filter_book_number}")
            else:
                chapter_list = all_chapters

            if max_chapters:
                chapter_list = chapter_list[:max_chapters]
                print(f"📝 Limiting to first {max_chapters} chapters for testing")

            # Step 3: Prepare metadata structure (will be updated after scraping)
            metadata = {
                "book_id": book_id,
                "book_title": book_title or "Unknown",
                "book_url": book_url,
                "filter_book_number": filter_book_number,
                "total_chapters_available": len(all_chapters),
                "chapters_to_scrape": len(chapter_list),
            }
            metadata_path = output_dir / "metadata.json"

            # Scrape each chapter
            successful_chapters = []
            failed_chapters = []

            print(f"\n🚀 Starting to scrape {len(chapter_list)} chapters...\n")

            for idx, chapter_info in enumerate(chapter_list, 1):
                # Check if we should stop
                if self._should_stop:
                    print(f"\n⚠️  Stopping at user request. Scraped {idx-1}/{len(chapter_list)} chapters.")
                    break

                chapter_num = chapter_info["number"]
                chapter_url = chapter_info["url"]
                print(f"[{idx}/{len(chapter_list)}] Scraping Chapter {chapter_num}: {chapter_info['title']}")

                try:
                    # Scrape chapter
                    chapter_data = self.scrape_chapter(chapter_url, chapter_num)

                    # Save text file with better naming
                    chapter_title = chapter_data.get("title", f"Chapter {chapter_num}")
                    text_filename = sanitize_chapter_filename(chapter_num, chapter_title)
                    text_path = chapters_dir / text_filename
                    text_path.write_text(chapter_data["content"], encoding="utf-8")

                    # Record success
                    bytes_downloaded = len(chapter_data["content"].encode("utf-8"))
                    self.metrics.record_chapter_download(
                        success=True, bytes_downloaded=bytes_downloaded, chapter_number=chapter_num
                    )

                    successful_chapters.append({
                        "number": chapter_num,
                        "title": chapter_data["title"],
                        "text_path": str(text_path),
                        "word_count": chapter_data["word_count"],
                    })
                    
                    # Update metadata tracker
                    tracker = MetadataTracker(output_dir)
                    tracker.mark_chapter_scraped(text_filename.replace('.txt', ''), chapter_data["word_count"])

                    # Rate limiting
                    if idx < len(chapter_list):
                        time.sleep(self.settings.scraper_delay_seconds)

                except Exception as e:
                    print(f"❌ Failed to scrape Chapter {chapter_num}: {e}")
                    failed_chapters.append({"number": chapter_num, "error": str(e)})
                    self.metrics.record_chapter_download(
                        success=False, error=str(e), chapter_number=chapter_num
                    )

                    # Retry logic could go here
                    if self.settings.scraper_retry_attempts > 0:
                        # TODO: Implement retry logic
                        pass

            # Update metadata with scraping results
            # Merge chapter info with scraping results
            chapters_metadata = []
            for ch_info in chapter_list:
                # Find matching successful chapter
                successful_ch = next(
                    (sc for sc in successful_chapters if sc["number"] == ch_info["number"]),
                    None,
                )
                if successful_ch:
                    chapters_metadata.append({
                        "number": ch_info["number"],
                        "title": ch_info["title"],
                        "url": ch_info["url"],
                        "text_path": successful_ch["text_path"],
                        "word_count": successful_ch["word_count"],
                    })
                else:
                    # Failed chapter - include basic info
                    failed_ch = next(
                        (fc for fc in failed_chapters if fc["number"] == ch_info["number"]),
                        None,
                    )
                    chapters_metadata.append({
                        "number": ch_info["number"],
                        "title": ch_info["title"],
                        "url": ch_info["url"],
                        "status": "failed",
                        "error": failed_ch["error"] if failed_ch else "Unknown error",
                    })

            metadata.update({
                "total_chapters": len(chapter_list),
                "successful_chapters": len(successful_chapters),
                "failed_chapters": len(failed_chapters),
                "chapters": chapters_metadata,
            })
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            print(f"💾 Updated metadata with scraping results")

            # Save metrics report
            metrics_path = self.metrics.save_report(f"{book_id}_scraper_metrics.json")
            self.metrics.print_summary()

            return {
                **metadata,
                "output_dir": str(output_dir),
                "metrics_path": str(metrics_path),
            }

        except Exception as e:
            self.metrics.stop()
            raise RuntimeError(f"Failed to scrape book: {e}") from e

