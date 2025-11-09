"""Metrics collector implementation."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.config import get_settings
from src.utils.metrics.scraper_metrics import ScraperMetrics


class MetricsCollector:
    """Collect and report metrics."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize metrics collector."""
        self.settings = get_settings()
        self.output_dir = output_dir or self.settings.data_dir / "metrics"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scraper_metrics = ScraperMetrics()
        self.start_time: Optional[float] = None

    def start(self):
        """Start timing."""
        self.start_time = time.time()

    def stop(self):
        """Stop timing and calculate totals."""
        if self.start_time:
            self.scraper_metrics.total_time_seconds = time.time() - self.start_time
            self.scraper_metrics.calculate_averages()

    def record_chapter_download(
        self,
        success: bool,
        bytes_downloaded: int = 0,
        error: Optional[str] = None,
        chapter_number: Optional[int] = None,
    ):
        """Record a chapter download attempt."""
        self.scraper_metrics.total_chapters += 1
        if success:
            self.scraper_metrics.successful_downloads += 1
            self.scraper_metrics.total_bytes_downloaded += bytes_downloaded
        else:
            self.scraper_metrics.failed_downloads += 1
            if error:
                self.scraper_metrics.errors.append(
                    {
                        "chapter": chapter_number,
                        "error": error,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    def record_text_quality(self, clean_text_ratio: float):
        """Record text extraction quality."""
        # Update running average
        current_avg = self.scraper_metrics.text_extraction_accuracy
        total = self.scraper_metrics.successful_downloads
        if total > 0:
            self.scraper_metrics.text_extraction_accuracy = (
                (current_avg * (total - 1) + clean_text_ratio) / total
            )

    def save_report(self, filename: str = "scraper_metrics.json") -> Path:
        """Save metrics report to JSON file."""
        self.stop()
        report_path = self.output_dir / filename
        with open(report_path, "w") as f:
            json.dump(self.scraper_metrics.to_dict(), f, indent=2)
        return report_path

    def print_summary(self):
        """Print human-readable summary."""
        self.stop()
        metrics = self.scraper_metrics
        print("\n" + "=" * 60)
        print("SCRAPER METRICS SUMMARY")
        print("=" * 60)
        print(f"Total Chapters: {metrics.total_chapters}")
        print(f"Successful: {metrics.successful_downloads}")
        print(f"Failed: {metrics.failed_downloads}")
        print(f"Success Rate: {(metrics.successful_downloads/metrics.total_chapters*100):.1f}%" if metrics.total_chapters > 0 else "N/A")
        print(f"Total Time: {metrics.total_time_seconds:.2f}s")
        print(f"Average per Chapter: {metrics.average_time_per_chapter:.2f}s")
        print(f"Total Data: {metrics.total_bytes_downloaded / 1024 / 1024:.2f} MB")
        print(f"Text Quality: {metrics.text_extraction_accuracy:.1f}%")
        if metrics.errors:
            print(f"\nErrors ({len(metrics.errors)}):")
            for error in metrics.errors[:5]:  # Show first 5
                print(f"  Chapter {error.get('chapter', '?')}: {error.get('error', 'Unknown')}")
        print("=" * 60 + "\n")

