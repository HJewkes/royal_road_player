"""Scraper metrics data model."""

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class ScraperMetrics:
    """Metrics for web scraping operations."""

    total_chapters: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_bytes_downloaded: int = 0
    total_time_seconds: float = 0.0
    average_time_per_chapter: float = 0.0
    text_extraction_accuracy: float = 0.0  # Percentage of clean text
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def calculate_averages(self):
        """Calculate average metrics."""
        if self.successful_downloads > 0:
            self.average_time_per_chapter = (
                self.total_time_seconds / self.successful_downloads
            )

