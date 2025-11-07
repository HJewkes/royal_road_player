"""Helper script to find books in a Royal Road series."""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup


def find_book_in_series(series_url: str, book_number: int) -> dict:
    """
    Find a specific book number in a Royal Road series.

    Args:
        series_url: URL to the series main page
        book_number: Book number to find (e.g., 7)

    Returns:
        Dictionary with book information or None
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(series_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")

        # Look for book references in the page
        text = soup.get_text().lower()
        
        # Check if this is a single fiction with chapters (not a series page)
        # If it has chapters, it might be the book itself
        chapter_links = soup.find_all("a", href=re.compile(r"/fiction/\d+/.+/chapter/\d+"))
        
        if chapter_links:
            # This might be the book itself - check page title/content for book number
            title = soup.find("title")
            title_text = title.get_text() if title else ""
            
            # Look for "Book X" in title or content
            book_match = re.search(r"book\s*(\d+)", text, re.I)
            if book_match:
                found_book_num = int(book_match.group(1))
                if found_book_num == book_number:
                    return {
                        "title": title_text,
                        "url": series_url,
                        "book_number": found_book_num,
                    }

        # Look for links to other books in the series
        # Royal Road sometimes lists related fictions
        related_links = soup.find_all("a", href=re.compile(r"/fiction/\d+"))
        
        for link in related_links:
            href = link.get("href", "")
            link_text = link.get_text().lower()
            
            # Check if link text mentions the book number
            if re.search(rf"book\s*{book_number}\b", link_text, re.I):
                full_url = f"https://www.royalroad.com{href}" if href.startswith("/") else href
                return {
                    "title": link.get_text(strip=True),
                    "url": full_url,
                    "book_number": book_number,
                }

        # If no direct match, return the series page info
        # User may need to navigate manually
        return {
            "title": soup.find("title").get_text() if soup.find("title") else "Unknown",
            "url": series_url,
            "book_number": None,
            "note": f"Could not find Book {book_number} directly. This may be the series page.",
        }

    except Exception as e:
        return {"error": str(e)}


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python scripts/find_book_series.py <series_url> <book_number>")
        print("Example: python scripts/find_book_series.py 'https://www.royalroad.com/fiction/58187/...' 7")
        sys.exit(1)

    series_url = sys.argv[1]
    try:
        book_number = int(sys.argv[2])
    except ValueError:
        print(f"Error: Book number must be an integer, got: {sys.argv[2]}")
        sys.exit(1)

    print(f"🔍 Looking for Book {book_number} in series: {series_url}\n")

    result = find_book_in_series(series_url, book_number)

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print(f"📚 Found:")
    print(f"   Title: {result.get('title', 'Unknown')}")
    print(f"   URL: {result.get('url')}")
    if result.get("book_number"):
        print(f"   Book Number: {result['book_number']}")
    if result.get("note"):
        print(f"   ⚠️  {result['note']}")

    print(f"\n💡 Use this URL with the scraper:")
    print(f"   python -m src.scraper.royal_road '{result['url']}'")


if __name__ == "__main__":
    main()

