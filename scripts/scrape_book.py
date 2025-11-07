#!/usr/bin/env python3
"""Command-line script for scraping Royal Road books."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.scraper.royal_road import RoyalRoadScraper


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape chapters from Royal Road")
    parser.add_argument(
        "url",
        type=str,
        help="Royal Road book URL (e.g., https://www.royalroad.com/fiction/12345/book-title)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory (defaults to data/books/{book_id})",
    )
    parser.add_argument(
        "-m",
        "--max-chapters",
        type=int,
        help="Maximum number of chapters to scrape (for testing)",
    )
    parser.add_argument(
        "-b",
        "--book-number",
        type=int,
        help="Filter chapters by book number (e.g., 7 for Book 7)",
    )

    args = parser.parse_args()

    scraper = RoyalRoadScraper()
    try:
        result = scraper.scrape_book(
            args.url, args.output, args.max_chapters, filter_book_number=args.book_number
        )
        print(f"\n✅ Successfully scraped {result['successful_chapters']}/{result['total_chapters']} chapters")
        print(f"📁 Output directory: {result['output_dir']}")
        print(f"📊 Metrics saved to: {result['metrics_path']}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

