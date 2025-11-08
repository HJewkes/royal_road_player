"""HTML processing and text extraction for Royal Road."""

import re
from typing import Optional, List, Dict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.models.responses import SearchResult
from src.scraper.formatter import TextFormatter

# Keep Dict import for backward compatibility with filter_chapters_by_book


class HTMLProcessor:
    """Process HTML from Royal Road to extract structured data."""
    
    def __init__(self):
        """Initialize HTML processor."""
        self.formatter = TextFormatter()
    
    def extract_book_id(self, url: str) -> str:
        """
        Extract book ID from Royal Road URL.
        
        Args:
            url: Royal Road book or chapter URL
            
        Returns:
            Book ID string (e.g., "book_12345")
            
        Raises:
            ValueError: If book ID cannot be extracted
        """
        match = re.search(r"/fiction/(\d+)", url)
        if match:
            return f"book_{match.group(1)}"
        raise ValueError(f"Could not extract book ID from URL: {url}")
    
    def extract_book_title(self, soup: BeautifulSoup, book_url: str) -> str:
        """
        Extract book title from Royal Road page.
        
        Args:
            soup: BeautifulSoup object of book page
            book_url: URL to the Royal Road book page (for fallback)
            
        Returns:
            Book title string
        """
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
    
    def sanitize_for_filesystem(self, name: str, max_length: int = 100, preserve_spaces: bool = True) -> str:
        """
        Sanitize a string for use in filesystem paths (directory or file names).
        
        This is typically used for HTML-extracted content like book titles that need
        to be filesystem-safe.
        
        Args:
            name: String to sanitize
            max_length: Maximum length of the sanitized string
            preserve_spaces: If True, keep spaces; if False, convert to hyphens
            
        Returns:
            Sanitized filesystem-safe string
        """
        # Remove or replace invalid characters
        # Keep alphanumeric, spaces, hyphens, underscores, and periods
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        
        if preserve_spaces:
            # Normalize whitespace (multiple spaces to single space)
            sanitized = re.sub(r'\s+', ' ', sanitized)
            # Remove leading/trailing spaces
            sanitized = sanitized.strip()
        else:
            # Replace multiple spaces/underscores/hyphens with single hyphen
            sanitized = re.sub(r'[\s_\-]+', '-', sanitized)
            # Remove leading/trailing dashes and dots
            sanitized = sanitized.strip('.-_')
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip('.-_ ')
        
        return sanitized if sanitized else "untitled"
    
    def extract_chapters(self, soup: BeautifulSoup, book_url: str, filter_book_number: Optional[int] = None) -> List[Dict]:
        """
        Extract chapter list from table of contents or book page.
        
        Args:
            soup: BeautifulSoup object of TOC or book page
            book_url: Base book URL for constructing full chapter URLs
            filter_book_number: Optional book number to filter chapters
            
        Returns:
            List of chapter dictionaries with url, number, and title
        """
        chapters = []
        chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")
        chapter_links = soup.find_all("a", href=chapter_pattern)
        
        for link in chapter_links:
            href = link.get("href", "")
            if not href:
                continue
            
            # Filter by book number if specified
            if filter_book_number:
                # Check URL for book-X pattern
                book_match = re.search(r"/book-(\d+)", href, re.I)
                if book_match:
                    book_num = int(book_match.group(1))
                    if book_num != filter_book_number:
                        continue
                
                # Check title text for book number
                link_text = link.get_text().lower()
                if f"book {filter_book_number}" not in link_text and f"book-{filter_book_number}" not in link_text:
                    # Check if it's clearly from a different book
                    other_book_match = re.search(r"book\s*(\d+)", link_text)
                    if other_book_match and int(other_book_match.group(1)) != filter_book_number:
                        continue
                    
                    # Check chapter numbering pattern (e.g., "7.1", "7.2")
                    chapter_num_match = re.search(r"^(\d+)\.", link_text)
                    if chapter_num_match:
                        chapter_book_num = int(chapter_num_match.group(1))
                        if chapter_book_num != filter_book_number:
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
    
    def extract_chapter_content(self, soup: BeautifulSoup) -> str:
        """
        Extract chapter text content from HTML.
        
        Args:
            soup: BeautifulSoup object of chapter page
            
        Returns:
            Chapter text content (formatted as markdown)
        """
        # Find the chapter content (usually in a div with class containing "chapter-content")
        content_div = (
            soup.find("div", class_=lambda x: x and "chapter-content" in str(x).lower()) or
            soup.find("div", class_=lambda x: x and "chapter" in str(x).lower() and "content" in str(x).lower()) or
            soup.find("div", id=lambda x: x and "chapter" in str(x).lower())
        )
        
        if not content_div:
            # Fallback: try to find main content area
            content_div = soup.find("div", class_=lambda x: x and "content" in str(x).lower())
        
        if not content_div:
            raise ValueError("Could not find chapter content in HTML")
        
        # Convert HTML to text using formatter
        html_content = str(content_div)
        text = self.formatter.html_to_text(html_content, preserve_paragraphs=True)
        text = self.formatter.clean_text(text)
        
        return text
    
    def extract_chapter_preview(self, soup: BeautifulSoup, max_length: int = 500) -> str:
        """
        Extract preview text from chapter (first N characters).
        
        Args:
            soup: BeautifulSoup object of chapter page
            max_length: Maximum length of preview text
            
        Returns:
            Preview text string
        """
        try:
            text = self.extract_chapter_content(soup)
            if len(text) > max_length:
                return text[:max_length] + "..."
            return text
        except Exception:
            return ""
    
    def extract_search_results(self, soup: BeautifulSoup) -> List[SearchResult]:
        """
        Extract search results from Royal Road search page.
        
        Args:
            soup: BeautifulSoup object of search results page
            
        Returns:
            List of SearchResult objects with title, author, and URL
        """
        results = []
        
        # Royal Road search results are typically in cards or list items
        # Look for fiction cards/items
        fiction_items = soup.find_all("div", class_=lambda x: x and "fiction" in str(x).lower())
        
        for item in fiction_items:
            # Find title link
            title_link = item.find("a", href=re.compile(r"/fiction/\d+"))
            if not title_link:
                continue
            
            title = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            if not href:
                continue
            
            full_url = urljoin("https://www.royalroad.com", href)
            
            # Find author (usually in a link or span)
            author_elem = item.find("a", href=re.compile(r"/profile/")) or item.find("span", class_=lambda x: x and "author" in str(x).lower())
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"
            
            results.append(SearchResult(
                title=title,
                author=author,
                url=full_url,
            ))
        
        return results
    
    def filter_chapters_by_book(self, chapters: List[Dict], book_number: int) -> List[Dict]:
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

