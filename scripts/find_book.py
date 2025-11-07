"""Helper script to find Royal Road book URLs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup


def search_royal_road(query: str) -> list[dict]:
    """
    Search Royal Road for a book.

    Args:
        query: Search query (book title or author)

    Returns:
        List of book dictionaries with title, author, and URL
    """
    search_url = "https://www.royalroad.com/fictions/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AudiobookBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    # Try different search parameter formats
    params_list = [
        {"title": query},
        {"q": query},
        {"search": query},
    ]

    for params in params_list:
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            results = []
            
            # Royal Road uses different structures - try multiple selectors
            # Look for fiction cards/rows
            fiction_cards = (
                soup.find_all("div", class_=lambda x: x and ("fiction" in str(x).lower() or "story" in str(x).lower()))
                or soup.find_all("tr", class_=lambda x: x and "fiction" in str(x).lower())
                or soup.find_all("li", class_=lambda x: x and "fiction" in str(x).lower())
            )

            # Also try direct links
            fiction_links = soup.find_all("a", href=lambda x: x and "/fiction/" in str(x) and "random" not in str(x))

            seen_urls = set()

            # Process cards/rows
            for card in fiction_cards[:10]:
                link = card.find("a", href=lambda x: x and "/fiction/" in str(x))
                if link:
                    href = link.get("href", "")
                    if href and "/fiction/" in href and "random" not in href:
                        full_url = f"https://www.royalroad.com{href}" if href.startswith("/") else href
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            title = link.get_text(strip=True) or card.get_text(strip=True)[:100]
                            
                            # Try to find author
                            author_elem = (
                                card.find("a", class_=lambda x: x and "author" in str(x).lower())
                                or card.find("span", class_=lambda x: x and "author" in str(x).lower())
                            )
                            author = author_elem.get_text(strip=True) if author_elem else "Unknown"

                            results.append({
                                "title": title,
                                "author": author,
                                "url": full_url,
                            })

            # Process direct links if no cards found
            if not results:
                for link in fiction_links[:10]:
                    href = link.get("href", "")
                    if href and "/fiction/" in href and "random" not in href:
                        full_url = f"https://www.royalroad.com{href}" if href.startswith("/") else href
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            title = link.get_text(strip=True)
                            
                            # Get parent to find author
                            parent = link.find_parent(["div", "tr", "li", "td"])
                            author = "Unknown"
                            if parent:
                                author_elem = parent.find("a", class_=lambda x: x and "author" in str(x).lower())
                                if author_elem:
                                    author = author_elem.get_text(strip=True)

                            results.append({
                                "title": title,
                                "author": author,
                                "url": full_url,
                            })

            if results:
                return results

        except Exception as e:
            continue  # Try next parameter format

    return []


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/find_book.py <search_query>")
        print("Example: python scripts/find_book.py 'Player Manager Ted Steele'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"🔍 Searching Royal Road for: {query}\n")

    results = search_royal_road(query)

    if not results:
        print("❌ No results found")
        print("\n💡 Try:")
        print("   1. Check the spelling")
        print("   2. Search on Royal Road directly: https://www.royalroad.com/fictions/search")
        print("   3. Provide the book URL directly to the scraper")
        sys.exit(1)

    print(f"📚 Found {len(results)} results:\n")
    for idx, book in enumerate(results, 1):
        print(f"{idx}. {book['title']}")
        print(f"   Author: {book['author']}")
        print(f"   URL: {book['url']}\n")

    print("💡 Copy the URL and use it with the scraper:")
    print("   python -m src.scraper.royal_road <URL>")


if __name__ == "__main__":
    main()

