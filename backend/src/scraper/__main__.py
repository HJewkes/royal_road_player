"""Command-line interface for Royal Road scraper."""

import argparse
import sys
from pathlib import Path

# Ensure backend is in path when running as module
if __name__ == "__main__":
    backend_path = Path(__file__).parent.parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

from src.scraper.royal_road_controller import RoyalRoadController


def main():
    """Main CLI entry point."""
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

    controller = RoyalRoadController()
    try:
        result = controller.scrape_book(
            book_url=args.url,
            output_dir=args.output,
            max_chapters=args.max_chapters,
            filter_book_number=args.book_number,
        )
        print(f"\n✅ Successfully scraped {result['successful_chapters']}/{result['chapters_to_scrape']} chapters")
        print(f"📁 Output directory: {result['output_dir']}")
        if 'metrics_path' in result:
            print(f"📊 Metrics saved to: {result['metrics_path']}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

