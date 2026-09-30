"""Tests for the job queue running several consumers at once.

process_fn is a fake that blocks briefly so jobs overlap; chunk bookkeeping on
disk is stubbed out, since the filesystem layout is covered by test_discovery.
"""

import asyncio
import threading
import time
from pathlib import Path

from src.queue.processor import JobQueue, JobStatus


class NullDiscovery:
    def mark_chunk_complete(self, *args):
        pass

    def mark_chunk_failed(self, *args):
        pass


class OverlapTracker:
    def __init__(self, fail_chunks=()):
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.rendered = []
        self.fail_chunks = set(fail_chunks)

    def __call__(self, job):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        with self._lock:
            self.active -= 1
            self.rendered.append(job.chunk_index)
        if job.chunk_index in self.fail_chunks:
            raise RuntimeError("synthesis failed")
        return Path(f"{job.chunk_index:03d}.wav"), 1.0


def _queue_with_chapter(chunks):
    queue = JobQueue()
    queue.chunk_discovery = NullDiscovery()
    queue.add_chapter("f1", 8, 16, [(i, f"text {i}") for i in range(1, chunks + 1)])
    return queue


async def _drain(queue, tracker, consumers, completions):
    async def on_chapter_complete(fiction_id, book, chapter):
        completions.append((fiction_id, book, chapter))

    async def on_chunk_complete(job):
        await asyncio.sleep(0.03)  # yields, letting the other consumer finish meanwhile

    await queue.start_processing(
        tracker,
        on_chunk_complete=on_chunk_complete,
        on_chapter_complete=on_chapter_complete,
        consumers=consumers,
    )
    while any(j.status in (JobStatus.PENDING, JobStatus.RUNNING) for j in queue._jobs.values()):
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)
    await queue.stop_processing()


def test_two_consumers_render_chunks_concurrently_and_each_exactly_once():
    queue, tracker, completions = _queue_with_chapter(6), OverlapTracker(), []

    asyncio.run(_drain(queue, tracker, consumers=2, completions=completions))

    assert tracker.peak == 2
    assert sorted(tracker.rendered) == [1, 2, 3, 4, 5, 6]


def test_chapter_completion_fires_once_with_concurrent_consumers():
    queue, tracker, completions = _queue_with_chapter(6), OverlapTracker(), []

    asyncio.run(_drain(queue, tracker, consumers=2, completions=completions))

    assert completions == [("f1", 8, 16)]


def test_single_consumer_never_overlaps_jobs():
    queue, tracker, completions = _queue_with_chapter(4), OverlapTracker(), []

    asyncio.run(_drain(queue, tracker, consumers=1, completions=completions))

    assert tracker.peak == 1
    assert completions == [("f1", 8, 16)]


def test_a_failed_chunk_does_not_stop_the_other_consumer():
    queue, tracker, completions = _queue_with_chapter(5), OverlapTracker(fail_chunks={2}), []

    asyncio.run(_drain(queue, tracker, consumers=2, completions=completions))

    statuses = {j.chunk_index: j.status for j in queue._jobs.values()}
    assert statuses[2] == JobStatus.FAILED
    assert all(statuses[i] == JobStatus.COMPLETED for i in (1, 3, 4, 5))


def test_status_reports_the_earliest_running_chunk_while_busy():
    queue, tracker, seen = _queue_with_chapter(4), OverlapTracker(), []

    async def run():
        await queue.start_processing(tracker, consumers=2)
        await asyncio.sleep(0.02)
        seen.append(queue.get_status().current_job_info.chunk_index)
        await queue.stop_processing()

    asyncio.run(run())

    assert seen == [1]
