"""Download job queue for tracking book download progress.

Tracks download jobs separately from audio processing jobs, allowing
users to monitor download progress in the UI.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    """Status of a download job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadJob:
    """A single book download job."""
    fiction_id: str
    book_number: int
    status: DownloadStatus = DownloadStatus.PENDING
    message: str = ""
    progress_chapters: int = 0
    total_chapters: int = 0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def job_id(self) -> str:
        """Unique job identifier."""
        return f"dl_{self.fiction_id}_{self.book_number}"

    @property
    def progress_percent(self) -> float:
        """Calculate download progress percentage."""
        if self.total_chapters == 0:
            return 0.0
        return (self.progress_chapters / self.total_chapters) * 100


class DownloadQueue:
    """In-memory queue for tracking download jobs."""

    _instance: Optional["DownloadQueue"] = None

    def __init__(self):
        """Initialize download queue."""
        self._jobs: dict[str, DownloadJob] = {}
        self._lock = asyncio.Lock()
        self._is_running = False
        self._processor_task: Optional[asyncio.Task] = None
        self._pending_queue: asyncio.Queue[DownloadJob] = asyncio.Queue()

    @classmethod
    def get_instance(cls) -> "DownloadQueue":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def add_job(
        self,
        fiction_id: str,
        book_number: int,
        total_chapters: int = 0,
    ) -> DownloadJob:
        """
        Add a download job to the queue.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            total_chapters: Expected number of chapters (for progress tracking)

        Returns:
            The created or existing job
        """
        job_id = f"dl_{fiction_id}_{book_number}"

        async with self._lock:
            # Check if job already exists and is running
            if job_id in self._jobs:
                existing = self._jobs[job_id]
                if existing.status in (DownloadStatus.PENDING, DownloadStatus.RUNNING):
                    logger.info(f"Download job {job_id} already in progress")
                    return existing
                # If completed/failed, allow re-download
                logger.info(f"Re-queueing download job {job_id}")

            job = DownloadJob(
                fiction_id=fiction_id,
                book_number=book_number,
                total_chapters=total_chapters,
                message="Queued for download",
            )
            self._jobs[job_id] = job
            await self._pending_queue.put(job)
            logger.info(f"Added download job: {job_id}")

        return job

    def update_progress(
        self,
        fiction_id: str,
        book_number: int,
        chapters_done: int,
        message: str = "",
    ):
        """Update download progress for a job."""
        job_id = f"dl_{fiction_id}_{book_number}"
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.progress_chapters = chapters_done
            if message:
                job.message = message

    def get_job(self, fiction_id: str, book_number: int) -> Optional[DownloadJob]:
        """Get a specific download job."""
        job_id = f"dl_{fiction_id}_{book_number}"
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[DownloadJob]:
        """Get all download jobs."""
        return list(self._jobs.values())

    def get_active_jobs(self) -> list[DownloadJob]:
        """Get all pending or running jobs."""
        return [
            j for j in self._jobs.values()
            if j.status in (DownloadStatus.PENDING, DownloadStatus.RUNNING)
        ]

    def get_status(self) -> dict:
        """Get queue status summary."""
        jobs = list(self._jobs.values())
        return {
            "pending": sum(1 for j in jobs if j.status == DownloadStatus.PENDING),
            "running": sum(1 for j in jobs if j.status == DownloadStatus.RUNNING),
            "completed": sum(1 for j in jobs if j.status == DownloadStatus.COMPLETED),
            "failed": sum(1 for j in jobs if j.status == DownloadStatus.FAILED),
            "is_processing": self._is_running,
            "jobs": [
                {
                    "job_id": j.job_id,
                    "fiction_id": j.fiction_id,
                    "book_number": j.book_number,
                    "status": j.status.value,
                    "message": j.message,
                    "progress_chapters": j.progress_chapters,
                    "total_chapters": j.total_chapters,
                    "progress_percent": j.progress_percent,
                }
                for j in jobs
                if j.status in (DownloadStatus.PENDING, DownloadStatus.RUNNING)
            ],
        }

    async def start_processing(
        self,
        download_fn: Callable[[str, int, Callable[[int, str], None]], None],
    ):
        """
        Start background processing of download jobs.

        Args:
            download_fn: Function to call for each download.
                         Signature: (fiction_id, book_number, progress_callback) -> None
                         Progress callback: (chapters_done, message) -> None
        """
        if self._is_running:
            logger.warning("Download processor already running")
            return

        self._is_running = True
        logger.info("Starting download processor...")

        async def process_loop():
            while self._is_running:
                try:
                    # Wait for next job with timeout
                    try:
                        job = await asyncio.wait_for(
                            self._pending_queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

                    # Process the job
                    job.status = DownloadStatus.RUNNING
                    job.started_at = datetime.utcnow()
                    job.message = "Downloading..."

                    try:
                        # Create progress callback
                        def on_progress(chapters_done: int, message: str):
                            self.update_progress(
                                job.fiction_id,
                                job.book_number,
                                chapters_done,
                                message,
                            )

                        # Run download in thread pool
                        await asyncio.to_thread(
                            download_fn,
                            job.fiction_id,
                            job.book_number,
                            on_progress,
                        )

                        job.status = DownloadStatus.COMPLETED
                        job.message = "Download complete"
                        job.completed_at = datetime.utcnow()
                        logger.info(f"Download complete: {job.job_id}")

                    except Exception as e:
                        job.status = DownloadStatus.FAILED
                        job.error = str(e)
                        job.message = f"Failed: {str(e)}"
                        job.completed_at = datetime.utcnow()
                        logger.error(f"Download failed: {job.job_id}: {e}")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in download processor: {e}")
                    await asyncio.sleep(1)

        self._processor_task = asyncio.create_task(process_loop())

    async def stop_processing(self):
        """Stop the background processor."""
        self._is_running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        logger.info("Download processor stopped")

    def clear_completed(self):
        """Remove completed and failed jobs from the queue."""
        to_remove = [
            job_id for job_id, job in self._jobs.items()
            if job.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED)
        ]
        for job_id in to_remove:
            del self._jobs[job_id]
        logger.info(f"Cleared {len(to_remove)} completed/failed download jobs")


# Singleton accessor
def get_download_queue() -> DownloadQueue:
    """Get the global download queue instance."""
    return DownloadQueue.get_instance()


