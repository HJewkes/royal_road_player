"""In-memory job queue with chapter-by-chapter processing.

Processes audio generation jobs one chunk at a time, prioritizing
completion of chapters before moving to the next.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
from collections import defaultdict

from src.config import get_settings
from src.discovery import ChunkDiscovery
from src.models import ChunkStatus, QueueStatus

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of a job in the queue."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """A single chunk processing job."""
    fiction_id: str
    book_number: int
    chapter_number: int
    chunk_index: int
    text: str
    priority: int = 0  # Higher = processed first
    status: JobStatus = JobStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def job_id(self) -> str:
        """Unique job identifier."""
        return f"{self.fiction_id}_{self.book_number}_{self.chapter_number}_{self.chunk_index}"

    @property
    def chapter_key(self) -> str:
        """Key to group jobs by chapter."""
        return f"{self.fiction_id}_{self.book_number}_{self.chapter_number}"


class JobQueue:
    """In-memory job queue with chapter-by-chapter processing."""

    def __init__(self):
        """Initialize job queue."""
        self.settings = get_settings()
        self.chunk_discovery = ChunkDiscovery()

        # Job storage
        self._jobs: dict[str, Job] = {}  # job_id -> Job
        self._chapter_jobs: dict[str, list[str]] = defaultdict(list)  # chapter_key -> [job_ids]

        # Processing state
        self._is_running = False
        self._current_job: Optional[Job] = None
        self._processor_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_chunk_complete: Optional[Callable] = None
        self._on_chapter_complete: Optional[Callable] = None

    def add_jobs(self, jobs: list[Job]) -> int:
        """
        Add jobs to the queue.

        Args:
            jobs: List of jobs to add

        Returns:
            Number of jobs added (excluding duplicates)
        """
        added = 0
        for job in jobs:
            if job.job_id not in self._jobs:
                self._jobs[job.job_id] = job
                self._chapter_jobs[job.chapter_key].append(job.job_id)
                added += 1
            else:
                logger.debug(f"Job {job.job_id} already exists, skipping")

        logger.info(f"Added {added} jobs to queue (total: {len(self._jobs)})")
        return added

    def add_chapter(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
        chunks: list[tuple[int, str]],
        priority: int = 0,
    ) -> int:
        """
        Add all pending chunks for a chapter to the queue.

        Args:
            fiction_id: Fiction ID
            book_number: Book number
            chapter_number: Chapter number
            chunks: List of (index, text) tuples
            priority: Job priority (higher = first)

        Returns:
            Number of jobs added
        """
        jobs = [
            Job(
                fiction_id=fiction_id,
                book_number=book_number,
                chapter_number=chapter_number,
                chunk_index=index,
                text=text,
                priority=priority,
            )
            for index, text in chunks
        ]
        return self.add_jobs(jobs)

    def get_next_job(self) -> Optional[Job]:
        """
        Get the next job to process.

        Strategy: Chapter-by-chapter processing
        1. Find chapters with pending jobs
        2. Sort by priority, then by chapter number
        3. Return the first pending chunk of the first incomplete chapter
        """
        # Group pending jobs by chapter
        chapter_pending: dict[str, list[Job]] = defaultdict(list)
        for job in self._jobs.values():
            if job.status == JobStatus.PENDING:
                chapter_pending[job.chapter_key].append(job)

        if not chapter_pending:
            return None

        # Sort chapters by priority (highest first), then by book number, then by chapter number
        def chapter_sort_key(chapter_key: str) -> tuple:
            jobs = chapter_pending[chapter_key]
            max_priority = max(j.priority for j in jobs)
            # Extract book and chapter number from key (format: fiction_id_book_chapter)
            # Use the job object directly for reliable parsing
            first_job = jobs[0]
            return (-max_priority, first_job.book_number, first_job.chapter_number)

        sorted_chapters = sorted(chapter_pending.keys(), key=chapter_sort_key)

        # Get the first pending job from the first chapter
        first_chapter = sorted_chapters[0]
        pending_jobs = sorted(chapter_pending[first_chapter], key=lambda j: j.chunk_index)

        return pending_jobs[0] if pending_jobs else None

    async def start_processing(
        self,
        process_fn: Callable[[Job], tuple[Path, float]],
        on_chunk_complete: Optional[Callable] = None,
        on_chapter_complete: Optional[Callable] = None,
    ) -> None:
        """
        Start background processing of jobs.

        Args:
            process_fn: Function to process a job, returns (audio_path, duration)
            on_chunk_complete: Callback when a chunk completes
            on_chapter_complete: Callback when all chunks for a chapter complete
        """
        if self._is_running:
            logger.warning("Processor already running")
            return

        self._on_chunk_complete = on_chunk_complete
        self._on_chapter_complete = on_chapter_complete
        self._is_running = True

        logger.info("Starting job processor...")
        self._processor_task = asyncio.create_task(self._process_loop(process_fn))

    async def stop_processing(self) -> None:
        """Stop the background processor."""
        self._is_running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        logger.info("Job processor stopped")

    async def _process_loop(self, process_fn: Callable) -> None:
        """Main processing loop."""
        while self._is_running:
            try:
                job = self.get_next_job()

                if job is None:
                    # No jobs to process, wait and check again
                    await asyncio.sleep(1)
                    continue

                # Process the job
                self._current_job = job
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()

                logger.info(f"Processing job: {job.job_id}")

                try:
                    # Run in thread pool to not block event loop
                    audio_path, duration = await asyncio.to_thread(
                        process_fn, job
                    )

                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()

                    # Mark chunk as complete in filesystem
                    self.chunk_discovery.mark_chunk_complete(
                        job.fiction_id,
                        job.book_number,
                        job.chapter_number,
                        job.chunk_index,
                        audio_path,
                    )

                    logger.info(f"✅ Completed: {job.job_id}")

                    # Trigger callback
                    if self._on_chunk_complete:
                        try:
                            await self._on_chunk_complete(job)
                        except Exception as e:
                            logger.error(f"Chunk callback error: {e}")

                    # Check if chapter is complete
                    if self._is_chapter_complete(job.chapter_key):
                        logger.info(f"📚 Chapter complete: {job.chapter_key}")
                        if self._on_chapter_complete:
                            try:
                                await self._on_chapter_complete(
                                    job.fiction_id,
                                    job.book_number,
                                    job.chapter_number,
                                )
                            except Exception as e:
                                logger.error(f"Chapter callback error: {e}")

                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.completed_at = datetime.utcnow()

                    # Mark chunk as failed in filesystem
                    self.chunk_discovery.mark_chunk_failed(
                        job.fiction_id,
                        job.book_number,
                        job.chapter_number,
                        job.chunk_index,
                        str(e),
                    )

                    logger.error(f"❌ Failed: {job.job_id} - {e}")

                finally:
                    self._current_job = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Processor error: {e}")
                await asyncio.sleep(1)

    def _is_chapter_complete(self, chapter_key: str) -> bool:
        """Check if all jobs for a chapter are complete."""
        job_ids = self._chapter_jobs.get(chapter_key, [])
        if not job_ids:
            return False

        for job_id in job_ids:
            job = self._jobs.get(job_id)
            if job and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                return False

        return True

    def get_status(self) -> QueueStatus:
        """Get current queue status with context about queued chapters."""
        from ..models import CurrentJobInfo, QueuedChapterInfo
        
        pending = sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING)
        running = sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)
        completed = sum(1 for j in self._jobs.values() if j.status == JobStatus.COMPLETED)
        failed = sum(1 for j in self._jobs.values() if j.status == JobStatus.FAILED)

        # Get current job info
        current_job_info = None
        if self._current_job:
            current_job_info = CurrentJobInfo(
                fiction_id=self._current_job.fiction_id,
                book_number=self._current_job.book_number,
                chapter_number=self._current_job.chapter_number,
                chunk_index=self._current_job.chunk_index,
            )

        # Get queued chapters summary (chapters with pending jobs)
        queued_chapters: list[QueuedChapterInfo] = []
        chapter_stats: dict[str, dict] = {}
        
        for job in self._jobs.values():
            if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                key = job.chapter_key
                if key not in chapter_stats:
                    chapter_stats[key] = {
                        'fiction_id': job.fiction_id,
                        'book_number': job.book_number,
                        'chapter_number': job.chapter_number,
                        'pending': 0,
                        'total': 0,
                        'max_priority': job.priority,
                    }
                chapter_stats[key]['pending'] += 1 if job.status == JobStatus.PENDING else 0
                chapter_stats[key]['total'] += 1
                # Track max priority for this chapter
                if job.priority > chapter_stats[key]['max_priority']:
                    chapter_stats[key]['max_priority'] = job.priority
        
        # Sort by processing order: highest priority first, then book number, then chapter number
        sorted_keys = sorted(
            chapter_stats.keys(),
            key=lambda k: (
                -chapter_stats[k]['max_priority'],
                chapter_stats[k]['book_number'],
                chapter_stats[k]['chapter_number'],
            )
        )
        
        for key in sorted_keys:
            stats = chapter_stats[key]
            queued_chapters.append(QueuedChapterInfo(
                fiction_id=stats['fiction_id'],
                book_number=stats['book_number'],
                chapter_number=stats['chapter_number'],
                pending_chunks=stats['pending'],
                total_chunks=stats['total'],
            ))

        return QueueStatus(
            pending=pending,
            running=running,
            completed=completed,
            failed=failed,
            is_processing=self._is_running,
            current_job=self._current_job.job_id if self._current_job else None,
            current_job_info=current_job_info,
            queued_chapters=queued_chapters[:10],  # Limit to first 10 chapters
        )

    def get_chapter_status(
        self,
        fiction_id: str,
        book_number: int,
        chapter_number: int,
    ) -> dict:
        """Get status for a specific chapter."""
        chapter_key = f"{fiction_id}_{book_number}_{chapter_number}"
        job_ids = self._chapter_jobs.get(chapter_key, [])

        pending = 0
        running = 0
        completed = 0
        failed = 0

        for job_id in job_ids:
            job = self._jobs.get(job_id)
            if job:
                if job.status == JobStatus.PENDING:
                    pending += 1
                elif job.status == JobStatus.RUNNING:
                    running += 1
                elif job.status == JobStatus.COMPLETED:
                    completed += 1
                elif job.status == JobStatus.FAILED:
                    failed += 1

        total = pending + running + completed + failed

        return {
            "chapter_number": chapter_number,
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "is_complete": pending == 0 and running == 0 and total > 0,
        }

    def retry_failed(self, job_id: Optional[str] = None) -> int:
        """
        Retry failed jobs.

        Args:
            job_id: Specific job to retry, or None to retry all

        Returns:
            Number of jobs queued for retry
        """
        count = 0
        for jid, job in self._jobs.items():
            if job.status == JobStatus.FAILED:
                if job_id is None or jid == job_id:
                    job.status = JobStatus.PENDING
                    job.error = None
                    job.started_at = None
                    job.completed_at = None
                    count += 1

        logger.info(f"Queued {count} jobs for retry")
        return count

    def clear_completed(self) -> int:
        """Remove completed jobs from memory."""
        to_remove = [
            job_id for job_id, job in self._jobs.items()
            if job.status == JobStatus.COMPLETED
        ]

        for job_id in to_remove:
            job = self._jobs[job_id]
            self._chapter_jobs[job.chapter_key].remove(job_id)
            del self._jobs[job_id]

        logger.info(f"Cleared {len(to_remove)} completed jobs")
        return len(to_remove)


# Singleton instance
_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get job queue singleton."""
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue

