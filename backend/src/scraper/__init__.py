"""Scraper module with pluggable source support."""

from typing import Protocol, Optional, Callable, runtime_checkable

from src.models import BookMetadata


@runtime_checkable
class Scraper(Protocol):
    """Protocol for content source scrapers."""

    def get_fiction_info(self, fiction_id: str) -> dict: ...

    def get_chapter_list(
        self, fiction_id: str, book_number: Optional[int] = None
    ) -> list[dict]: ...

    def download_chapter_text(self, chapter_ref: str) -> str: ...

    def download_book(
        self,
        fiction_id: str,
        book_number: int,
        delay: float = 1.0,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> BookMetadata: ...


def get_scraper(source: str = "royal_road") -> Scraper:
    """Get scraper instance for the given source."""
    if source == "patreon":
        from src.scraper.patreon import PatreonScraper
        return PatreonScraper()
    from src.scraper.royal_road import RoyalRoadScraper
    return RoyalRoadScraper()
