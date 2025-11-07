"""Discover books and chapters from filesystem."""

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.utils.config import get_settings
from src.utils.metadata_tracker import MetadataTracker


# Import search functions from scraper
from src.scraper.royal_road import RoyalRoadScraper


def search_royal_road(query: str) -> list[dict]:
    """
    Search Royal Road for a book.
    
    Wrapper function that uses RoyalRoadScraper.

    Args:
        query: Search query (book title or author)

    Returns:
        List of book dictionaries with title, author, and URL
    """
    scraper = RoyalRoadScraper()
    return scraper.search_royal_road(query)


def find_book_in_series(series_url: str, book_number: int) -> dict:
    """
    Find a specific book number in a Royal Road series.
    
    Wrapper function that uses RoyalRoadScraper.

    Args:
        series_url: URL to the series main page
        book_number: Book number to find (e.g., 7)

    Returns:
        Dictionary with book information or error
    """
    scraper = RoyalRoadScraper()
    return scraper.find_book_in_series(series_url, book_number)


def discover_books() -> list[dict]:
    """
    Discover all books from the filesystem.
    
    Returns:
        List of book dictionaries with metadata
    """
    settings = get_settings()
    books_dir = settings.books_dir
    
    if not books_dir.exists():
        return []
    
    books = []
    
    for book_dir in books_dir.iterdir():
        if not book_dir.is_dir():
            continue
        
        # Try to load metadata.json
        metadata_path = book_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                book_id = metadata.get('book_id', book_dir.name)
                book_title = metadata.get('book_title', book_dir.name)
                book_url = metadata.get('book_url', '')
                
                # Count chapters
                chapters_dir = book_dir / "chapters"
                chapter_count = 0
                if chapters_dir.exists():
                    chapter_count = len(list(chapters_dir.glob("*.txt")))
                
                # Get progress stats from metadata tracker
                tracker = MetadataTracker(book_dir)
                tracker.refresh_from_filesystem()  # Ensure stats are up to date
                stats = tracker.get_stats()
                
                books.append({
                    'id': book_id,
                    'title': book_title,
                    'author': None,  # Not in metadata yet
                    'url': book_url,
                    'chapter_count': chapter_count,
                    'path': str(book_dir),
                    'stats': stats,
                })
            except (json.JSONDecodeError, KeyError) as e:
                # Skip invalid metadata files
                continue
    
    return books


def discover_chapters(book_id: str) -> list[dict]:
    """
    Discover chapters for a book.
    
    Args:
        book_id: Book identifier
        
    Returns:
        List of chapter dictionaries
    """
    settings = get_settings()
    books_dir = settings.books_dir
    
    # Find book directory
    book_dir = None
    for dir_path in books_dir.iterdir():
        if dir_path.is_dir() and book_id in dir_path.name:
            # Check metadata.json to confirm book_id
            metadata_path = dir_path / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        book_dir = dir_path
                        break
                except (json.JSONDecodeError, KeyError):
                    continue
    
    if not book_dir:
        return []
    
    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        return []
    
    chapters = []
    
    # Load metadata tracker for chapter info
    tracker = MetadataTracker(book_dir)
    tracker.refresh_from_filesystem()  # Ensure stats are up to date
    metadata = tracker.load()
    chapter_metadata = {ch.get('title'): ch for ch in metadata.get('chapters', [])}
    
    # Find all text files (chapters)
    text_files = sorted(chapters_dir.glob("*.txt"))
    
    for idx, text_file in enumerate(text_files, 1):
        chapter_title = text_file.stem
        
        # Get metadata if available
        meta = chapter_metadata.get(chapter_title, {})
        
        # Find audio files (could be single file or chunks)
        audio_files = list(chapters_dir.glob(f"{chapter_title}*.wav"))
        has_audio = len(audio_files) > 0
        
        # Check if it's chunked - always check filesystem first
        chunk_files = list(chapters_dir.glob(f"{chapter_title}_chunk_*.wav"))
        is_chunked = len(chunk_files) > 0
        chunk_count = len(chunk_files) if is_chunked else (meta.get('chunk_count', 0))
        
        # Update metadata if we found chunks that weren't tracked
        if is_chunked and chunk_count > 0 and chunk_count != meta.get('chunk_count', 0):
            tracker.update_chunk_count(chapter_title, chunk_count)
            tracker.mark_chapter_audio_generated(chapter_title)
        
        chapters.append({
            'id': idx,
            'chapter_number': idx,
            'title': chapter_title,
            'text_path': str(text_file),
            'audio_paths': [str(f) for f in sorted(audio_files)] if has_audio else [],
            'is_chunked': is_chunked,
            'chunk_count': chunk_count,
            'has_audio': has_audio or meta.get('has_audio', False),
            'scraped': meta.get('scraped', True),  # If file exists, it's scraped
            'word_count': meta.get('word_count'),
            'duration_seconds': None,  # Would need to calculate from audio
        })
    
    return chapters


def get_chapter_audio_urls(book_id: str, chapter_title: str) -> list[str]:
    """
    Get audio file URLs for a chapter.
    
    Args:
        book_id: Book identifier
        chapter_title: Chapter title (filename without extension)
        
    Returns:
        List of audio file URLs (relative to /audio mount)
    """
    settings = get_settings()
    books_dir = settings.books_dir
    
    # Find book directory
    book_dir = None
    for dir_path in books_dir.iterdir():
        if dir_path.is_dir() and book_id in dir_path.name:
            metadata_path = dir_path / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        book_dir = dir_path
                        break
                except (json.JSONDecodeError, KeyError):
                    continue
    
    if not book_dir:
        return []
    
    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        return []
    
    # Find audio files
    audio_files = sorted(chapters_dir.glob(f"{chapter_title}*.wav"))
    
    # Convert to URLs relative to /audio mount
    # Path: data/books/Book Name (book_id)/chapters/file.wav
    # URL: /audio/Book Name (book_id)/chapters/file.wav
    urls = []
    for audio_file in audio_files:
        # Get relative path from books_dir
        rel_path = audio_file.relative_to(books_dir)
        urls.append(f"/audio/{rel_path.as_posix()}")
    
    return urls


def fetch_book_preview(book_url: str, book_number: Optional[int] = None) -> dict:
    """
    Fetch preview information for a book from Royal Road.
    
    Args:
        book_url: URL to the Royal Road book page
        book_number: Optional book number to filter chapters
        
    Returns:
        Dictionary with chapter_count, chapters (list with titles), and preview_text
    """
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        
        # Get table of contents
        toc_url = book_url.rstrip("/") + "/table-of-contents"
        response = session.get(toc_url, timeout=30)
        
        if response.status_code != 200:
            response = session.get(book_url, timeout=30)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        
        # Find all chapter links
        chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")
        chapter_links = soup.find_all("a", href=chapter_pattern)
        
        chapters = []
        for link in chapter_links:
            href = link.get("href", "")
            link_text = link.get_text(strip=True)
            
            if not href:
                continue
            
            # Filter by book number if specified
            if book_number:
                # Check XX-YY pattern
                title_match = re.search(r'^(\d{1,2})-\d+', link_text)
                if title_match and int(title_match.group(1)) != book_number:
                    continue
                
                # Check X.Y pattern
                title_match2 = re.search(r'^(\d+)\.\d+', link_text)
                if title_match2 and int(title_match2.group(1)) != book_number:
                    continue
                
                # Check /book-X in URL
                url_match = re.search(r'/book-(\d+)', href, re.I)
                if url_match and int(url_match.group(1)) != book_number:
                    continue
            
            full_url = urljoin("https://www.royalroad.com", href)
            chapters.append({
                'title': link_text,
                'url': full_url,
            })
        
        # Get preview text from first chapter
        preview_text = ""
        if chapters:
            try:
                first_chapter_url = chapters[0]['url']
                chapter_response = session.get(first_chapter_url, timeout=30)
                chapter_response.raise_for_status()
                chapter_soup = BeautifulSoup(chapter_response.content, "lxml")
                
                # Find the chapter content (usually in a div with class containing "chapter-content" or similar)
                content_div = (
                    chapter_soup.find("div", class_=lambda x: x and "chapter-content" in str(x).lower()) or
                    chapter_soup.find("div", class_=lambda x: x and "chapter" in str(x).lower() and "content" in str(x).lower()) or
                    chapter_soup.find("div", id=lambda x: x and "chapter" in str(x).lower())
                )
                
                if content_div:
                    # Get text and take first 500 characters
                    text = content_div.get_text(strip=True)
                    preview_text = text[:500] + "..." if len(text) > 500 else text
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Failed to fetch preview text: {e}")
        
        return {
            'chapter_count': len(chapters),
            'chapters': chapters[:20],  # Limit to first 20 for preview
            'preview_text': preview_text,
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fetch book preview: {e}")
        return {
            'chapter_count': 0,
            'chapters': [],
            'preview_text': '',
        }


def fetch_series_books_from_royal_road(book_url: str) -> list[dict]:
    """
    Fetch all books in a series from Royal Road by analyzing chapter URLs.
    
    Args:
        book_url: URL to the Royal Road book page
        
    Returns:
        List of book dictionaries with book_number and inferred URLs
    """
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        
        # Get table of contents
        toc_url = book_url.rstrip("/") + "/table-of-contents"
        response = session.get(toc_url, timeout=30)
        
        if response.status_code != 200:
            response = session.get(book_url, timeout=30)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        
        # Extract fiction ID
        fiction_match = re.search(r'/fiction/(\d+)', book_url)
        if not fiction_match:
            return []
        fiction_id = fiction_match.group(1)
        
        # Find all chapter links
        chapter_pattern = re.compile(r"/fiction/\d+/.+/chapter/\d+")
        chapter_links = soup.find_all("a", href=chapter_pattern)
        
        book_numbers = set()
        chapter_data = []  # Store chapter info for analysis
        
        # Analyze all chapters to find book numbers
        for link in chapter_links:
            href = link.get("href", "")
            link_text = link.get_text(strip=True)
            
            # Method 1: Look for /book-X pattern in URL
            book_match = re.search(r'/book-(\d+)', href, re.I)
            if book_match:
                book_numbers.add(int(book_match.group(1)))
            
            # Method 2: Look for book numbers in chapter titles
            # Patterns like "07-01" (book 7, chapter 1), "7.1", "Book 7 Chapter 1", etc.
            # Pattern: XX-YY where XX is book number (most common for Royal Road)
            title_book_match = re.search(r'^(\d{1,2})-\d+', link_text)
            if title_book_match:
                book_num = int(title_book_match.group(1))
                book_numbers.add(book_num)
            
            # Pattern: X.Y where X is book number
            title_book_match2 = re.search(r'^(\d+)\.\d+', link_text)
            if title_book_match2:
                book_num = int(title_book_match2.group(1))
                book_numbers.add(book_num)
            
            # Pattern: "Book X" in title (anywhere in the title)
            title_book_match3 = re.search(r'\bBook\s*(\d+)\b', link_text, re.I)
            if title_book_match3:
                book_num = int(title_book_match3.group(1))
                book_numbers.add(book_num)
            
            # Pattern: Look for single-digit prefixes that might be book numbers
            # e.g., "1. Chapter Title" or "1 - Chapter Title" (but be careful not to match chapter numbers)
            # Only match if it's at the start and followed by punctuation
            single_digit_match = re.search(r'^(\d)[\s\.-]+[A-Z]', link_text)
            if single_digit_match:
                potential_book = int(single_digit_match.group(1))
                # Only consider if it's a reasonable book number (1-20)
                if 1 <= potential_book <= 20:
                    book_numbers.add(potential_book)
            
            # Extract chapter number for analysis
            chapter_match = re.search(r'/chapter/(\d+)', href)
            if chapter_match:
                chapter_num = int(chapter_match.group(1))
                chapter_data.append({
                    'number': chapter_num,
                    'title': link_text,
                    'url': href,
                })
        
        # Method 3: Analyze chapter data more thoroughly
        # Look for XX-YY pattern in ALL chapter titles (not just first match)
        if chapter_data:
            for ch in chapter_data:
                # XX-YY pattern (most reliable)
                pattern_match = re.search(r'^(\d{1,2})-\d+', ch['title'])
                if pattern_match:
                    book_num = int(pattern_match.group(1))
                    book_numbers.add(book_num)
                
                # X.Y pattern
                pattern_match2 = re.search(r'^(\d+)\.\d+', ch['title'])
                if pattern_match2:
                    book_num = int(pattern_match2.group(1))
                    book_numbers.add(book_num)
                
                # "Book X" anywhere in title
                pattern_match3 = re.search(r'\bBook\s*(\d+)\b', ch['title'], re.I)
                if pattern_match3:
                    book_num = int(pattern_match3.group(1))
                    book_numbers.add(book_num)
        
        # Build list of series books - ONLY include books we actually detected
        series_books = []
        
        # Only add books we actually found on Royal Road
        if book_numbers:
            for book_num in sorted(book_numbers):
                series_books.append({
                    'book_number': book_num,
                    'url': book_url,  # Same URL, filter by book number when scraping
                    'title': f"Book {book_num}",  # Will be updated when scraped
                    'in_system': False,
                })
        # If no books detected, return empty list (don't guess)
        
        return series_books
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fetch series from Royal Road: {e}")
        return []


def find_series_books(book_id: str) -> list[dict]:
    """
    Find other books in the same series (both in system and from Royal Road).
    
    Args:
        book_id: Book ID to find series for
        
    Returns:
        List of book dictionaries in the same series
    """
    settings = get_settings()
    books_dir = settings.books_dir
    
    # Find the target book
    target_book = None
    target_book_dir = None
    for book_dir in books_dir.iterdir():
        if not book_dir.is_dir():
            continue
        
        metadata_path = book_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                if metadata.get('book_id') == book_id:
                    target_book = metadata
                    target_book_dir = book_dir
                    break
            except Exception:
                continue
    
    if not target_book:
        return []
    
    # Extract series identifier
    target_url = target_book.get('book_url', '')
    target_title = target_book.get('book_title', '')
    
    # Extract base title (without "Book X" suffix)
    base_title_match = re.sub(r'\s*-\s*Book\s*\d+.*$', '', target_title, flags=re.I)
    base_title_match = re.sub(r'\s*\(book_\d+\)', '', base_title_match, flags=re.I).strip()
    
    # Extract fiction ID from URL
    url_match = re.search(r'/fiction/(\d+)', target_url)
    base_fiction_id = url_match.group(1) if url_match else None
    
    series_books = []
    books_in_system = {}  # Map book_number -> book dict
    
    # Add the current book to books_in_system first
    target_book_number = target_book.get('filter_book_number')
    if not target_book_number:
        # Try to extract from title
        book_num_match = re.search(r'Book\s*(\d+)', target_title, re.I)
        if book_num_match:
            target_book_number = int(book_num_match.group(1))
        else:
            # Try to extract from chapter files
            chapters_dir = target_book_dir / "chapters"
            if chapters_dir.exists():
                chapter_files = sorted(chapters_dir.glob("*.txt"))[:3]
                for ch_file in chapter_files:
                    ch_match = re.search(r'(\d{1,2})-\d+', ch_file.stem)
                    if ch_match:
                        target_book_number = int(ch_match.group(1))
                        break
    
    if target_book_number:
        chapters_dir = target_book_dir / "chapters"
        has_audio = False
        if chapters_dir.exists():
            has_audio = len(list(chapters_dir.glob("*.wav"))) > 0
        
        books_in_system[target_book_number] = {
            'id': book_id,
            'title': target_title,
            'book_number': target_book_number,
            'url': target_url,
            'has_audio': has_audio,
            'in_system': True,
        }
        series_books.append(books_in_system[target_book_number])
    
    # Look for other books with same base title or fiction ID (already in system)
    for book_dir in books_dir.iterdir():
        if not book_dir.is_dir() or book_dir == target_book_dir:
            continue
        
        metadata_path = book_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                book_id_other = metadata.get('book_id')
                if book_id_other == book_id:
                    continue
                
                book_url = metadata.get('book_url', '')
                book_title = metadata.get('book_title', '')
                
                # Check if same fiction ID
                is_same_series = False
                book_number = None
                
                if base_fiction_id and book_url:
                    other_url_match = re.search(r'/fiction/(\d+)', book_url)
                    if other_url_match and other_url_match.group(1) == base_fiction_id:
                        is_same_series = True
                
                # Also check by base title similarity
                if not is_same_series and base_title_match:
                    other_base_title = re.sub(r'\s*-\s*Book\s*\d+.*$', '', book_title, flags=re.I)
                    other_base_title = re.sub(r'\s*\(book_\d+\)', '', other_base_title, flags=re.I).strip()
                    if base_title_match.lower() == other_base_title.lower() and base_title_match:
                        is_same_series = True
                
                if is_same_series:
                    # Extract book number - try multiple methods
                    book_number = None
                    
                    # Method 1: Extract from title (e.g., "Book 7" or "Book 7 - Title")
                    book_num_match = re.search(r'Book\s*(\d+)', book_title, re.I)
                    if book_num_match:
                        book_number = int(book_num_match.group(1))
                    
                    # Method 2: Check filter_book_number in metadata (most reliable)
                    if not book_number:
                        book_number = metadata.get('filter_book_number')
                    
                    # Method 3: Try to extract from directory name or chapter titles
                    if not book_number:
                        # Look at first few chapter files for pattern
                        chapters_dir = book_dir / "chapters"
                        if chapters_dir.exists():
                            chapter_files = sorted(chapters_dir.glob("*.txt"))[:3]
                            for ch_file in chapter_files:
                                # Look for XX-YY pattern in filename
                                ch_match = re.search(r'(\d{1,2})-\d+', ch_file.stem)
                                if ch_match:
                                    book_number = int(ch_match.group(1))
                                    break
                    
                    # Check for audio
                    chapters_dir = book_dir / "chapters"
                    has_audio = False
                    if chapters_dir.exists():
                        has_audio = len(list(chapters_dir.glob("*.wav"))) > 0
                    
                    book_dict = {
                        'id': book_id_other,
                        'title': book_title,
                        'book_number': book_number,
                        'url': book_url,
                        'has_audio': has_audio,
                        'in_system': True,
                    }
                    series_books.append(book_dict)
                    if book_number:
                        books_in_system[book_number] = book_dict
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Error checking book {book_dir.name}: {e}")
                continue
    
    # Fetch series books from Royal Road
    if target_url:
        royal_road_books = fetch_series_books_from_royal_road(target_url)
        for rr_book in royal_road_books:
            book_num = rr_book.get('book_number')
            # Check if this book is already in system (by book number)
            if book_num in books_in_system:
                # Use the existing book info instead
                existing_book = books_in_system[book_num]
                # Update with Royal Road info if needed
                if not existing_book.get('url'):
                    existing_book['url'] = rr_book.get('url', target_url)
                # Don't add duplicate
                continue
            # Only add if not already in system
            if book_num:
                series_books.append(rr_book)
    
    # Sort by book number
    series_books.sort(key=lambda x: x.get('book_number', 999))
    
    return series_books

