"""Job queue service for processing chunks sequentially."""

import asyncio
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Tuple, Set

from src.controllers.tts_controller import TTSController
from src.data.database import db_session
from src.data.db_repository import ChapterRepository, ChunkRepository
from src.models.chunk import Chunk
from src.models.enums import ChunkStatus
from src.services.chunk_job import ChunkJob
from src.services.job_status import JobStatus
from src.services.queue_events import get_event_manager
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class ChunkJobQueue:
    """Queue manager for processing chunks sequentially. Uses database as single source of truth."""
    
    def __init__(self):
        """Initialize job queue. No longer uses file-based queue - all state in database."""
        self.settings = get_settings()
        
        self._processing = False
        self._current_chunk_id: Optional[str] = None  # Track current processing chunk by ID
        self._tts_controller: Optional[TTSController] = None
        self._processor_task: Optional[asyncio.Task] = None  # Keep reference to background task
        self._last_recovery_time: float = 0.0  # Track when we last ran recovery
        self._recovery_interval: float = 30.0  # Only recover every 30 seconds
        self._retried_failed_chunks: Set[str] = set()  # Track failed chunks retried in this processor run
        
        # Recover any stuck jobs on startup
        self.recover_stuck_jobs()
    
    def enqueue_chunks(
        self,
        chunks: List[Chunk],
        chapter_number: Optional[int] = None,
        speaker: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> int:
        """
        Add chunks to the processing queue by updating their DB status to PENDING.
        
        Args:
            chunks: List of Chunk objects to queue
            speaker: Optional speaker/voice name for all chunks (stored in chunk)
            speed: Optional speed for all chunks (stored in chunk)
            
        Returns:
            Number of chunks queued
        """
        added = 0
        skipped_completed = 0
        skipped_pending_or_running = 0
        
        for chunk in chunks:
            # Skip if already completed (has audio AND status is completed)
            if chunk.is_completed:
                skipped_completed += 1
                logger.debug(f"Skipping completed chunk {chunk.index} (status={chunk.status.value}, has_audio={chunk.has_audio})")
                continue
            
            # Get chapter number from parameter or chunk's chapter_id
            job_chapter_number = chapter_number
            if job_chapter_number is None:
                if chunk.chapter_id:
                    # Extract chapter number from chapter_id (format: book_id_XX)
                    parts = chunk.chapter_id.split('_')
                    if len(parts) >= 2:
                        try:
                            job_chapter_number = int(parts[-1])
                        except ValueError:
                            pass
                
                if job_chapter_number is None:
                    # Try to load from DB
                    chapter = ChapterRepository.get_by_id(chunk.chapter_id)
                    if chapter:
                        job_chapter_number = chapter.chapter_number
                
                if job_chapter_number is None:
                    job_chapter_number = 0
            
            # Check current status in DB
            chunk_db = ChunkRepository.get_by_book_chapter_index(
                chunk.book_id, job_chapter_number, chunk.index
            )
            
            if chunk_db:
                # Skip if already PENDING or RUNNING
                if chunk_db.status in (ChunkStatus.PENDING, ChunkStatus.RUNNING):
                    skipped_pending_or_running += 1
                    logger.debug(f"Chunk {chunk.index} already {chunk_db.status.value}, skipping")
                    continue
                
                # Update voice_name and speed if provided
                if speaker or speed is not None:
                    chunk_db.voice_name = speaker or chunk_db.voice_name
                    chunk_db.speed = speed if speed is not None else chunk_db.speed
                    ChunkRepository.create_or_update(
                        ChunkRepository._to_model(chunk_db), 
                        job_chapter_number
                    )
            
            # Set status to PENDING (this will clear error and processing_started_at)
            ChunkRepository.update_status(
                chunk.book_id, 
                job_chapter_number, 
                chunk.index, 
                ChunkStatus.PENDING,
                error=None  # Clear any previous errors
            )
            added += 1
        
        if added == 0 and len(chunks) > 0:
            logger.warning(
                f"⚠️ No chunks queued despite {len(chunks)} provided! "
                f"Skipped {skipped_completed} completed, {skipped_pending_or_running} already pending/running"
            )
        else:
            logger.info(
                f"✅ Queued {added} chunks. "
                f"Skipped {skipped_completed} completed, {skipped_pending_or_running} already pending/running"
            )
        return added
    
    def enqueue_chapter_chunks(
        self,
        book_id: str,
        chapter_number: int,
        chunk_indices: Optional[List[int]] = None,
        speaker: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> int:
        """
        Add chunks from a chapter to the processing queue.
        
        Args:
            book_id: Book identifier
            chapter_number: Chapter number
            chunk_indices: Optional list of chunk indices (defaults to all pending chunks)
            speaker: Optional speaker/voice name
            speed: Optional speed
            
        Returns:
            Number of jobs added to queue
        """
        chunks = ChunkRepository.get_by_chapter(book_id, chapter_number)
        
        if not chunks:
            logger.warning(f"No chunks found for chapter {chapter_number}")
            return 0
        
        logger.info(f"Found {len(chunks)} total chunks for chapter {chapter_number}")
        
        # Filter chunks if indices specified
        if chunk_indices is not None:
            chunks = [ch for ch in chunks if ch.index in chunk_indices]
            logger.info(f"Filtered to {len(chunks)} chunks by indices")
        else:
            # Queue pending chunks, or failed chunks (for retry)
            # Failed chunks can be retried by re-queuing them
            pending_count = sum(1 for ch in chunks if ch.is_pending)
            failed_count = sum(1 for ch in chunks if ch.is_failed)
            logger.info(f"Found {pending_count} pending and {failed_count} failed chunks")
            chunks = [ch for ch in chunks if ch.is_pending or ch.is_failed]
            logger.info(f"Filtered to {len(chunks)} chunks (pending + failed)")
        
        # Reset failed chunks to PENDING status in database so they can be retried
        failed_chunks_to_reset = [ch for ch in chunks if ch.is_failed]
        logger.info(f"Found {len(failed_chunks_to_reset)} failed chunks to reset (out of {len(chunks)} total chunks)")
        
        if failed_chunks_to_reset:
            logger.info(f"Resetting {len(failed_chunks_to_reset)} failed chunks to PENDING in database for retry")
            reset_count = 0
            for chunk in failed_chunks_to_reset:
                try:
                    # Reset status in database
                    ChunkRepository.update_status(
                        chunk.book_id,
                        chapter_number,
                        chunk.index,
                        ChunkStatus.PENDING,
                        error=None  # Clear error message
                    )
                    reset_count += 1
                    logger.debug(f"✅ Reset chunk {chunk.index} to PENDING in database")
                except Exception as e:
                    logger.error(f"Error resetting chunk {chunk.index} to PENDING: {e}", exc_info=True)
            logger.info(f"✅ Reset {reset_count}/{len(failed_chunks_to_reset)} failed chunks to PENDING in database")
            
            # Update chunks list in memory - mark failed chunks as pending
            for i, chunk in enumerate(chunks):
                if chunk.is_failed:
                    updated_chunk = Chunk(
                        index=chunk.index,
                        book_id=chunk.book_id,
                        text_start=chunk.text_start,
                        text_end=chunk.text_end,
                        status=ChunkStatus.PENDING,
                        chapter_id=chunk.chapter_id,
                        path=chunk.path,
                        generation_time_seconds=chunk.generation_time_seconds,
                        voice_name=chunk.voice_name,
                        speed=chunk.speed,
                        pre_pause_ms=chunk.pre_pause_ms,
                        post_pause_ms=chunk.post_pause_ms,
                        is_dialogue=chunk.is_dialogue,
                        is_scene_break=chunk.is_scene_break,
                    )
                    chunks[i] = updated_chunk
            
            logger.info(f"After reset, have {len(chunks)} chunks ready to enqueue ({sum(1 for c in chunks if c.is_pending)} pending)")

        if not chunks:
            logger.warning(f"No chunks to enqueue for chapter {chapter_number} after filtering")
            return 0

        logger.info(f"Enqueuing {len(chunks)} chunks")
        logger.info(f"Chunk statuses: {[f'{c.index}={c.status.value}' for c in chunks[:10]]}")
        added = self.enqueue_chunks(chunks, chapter_number=chapter_number, speaker=speaker, speed=speed)
        logger.info(f"Successfully added {added} jobs to queue")
        return added
    
    def recover_stuck_jobs(self) -> int:
        """
        Recover chunks stuck in RUNNING state (e.g., after server crash).
        Queries database for RUNNING chunks and checks if they're actually stuck.
        
        If background processor is disabled, all RUNNING chunks are considered stuck
        and will be recovered immediately.
        
        Returns:
            Number of chunks recovered
        """
        recovered = 0
        with db_session() as session:
            # Find all RUNNING chunks using repository
            running_chunks = ChunkRepository.get_running_chunks(session=session)
            
            # If background processor is disabled, all RUNNING chunks are stuck
            processor_enabled = self.settings.enable_background_processor
            
            # Check if processor is actually processing (has current_job)
            # If processor is enabled but has no current job, all RUNNING chunks are likely stuck
            processor_actually_processing = (
                processor_enabled and 
                self._current_chunk_id is not None and 
                self._processing
            )
            
            for chunk_db in running_chunks:
                # Check if processing_started_at is old (> 2 minutes) or processor is disabled
                should_recover = False
                if not processor_enabled:
                    # Processor disabled - all RUNNING chunks are stuck
                    should_recover = True
                elif not processor_actually_processing:
                    # Processor enabled but not actually processing - all RUNNING chunks are stuck
                    should_recover = True
                elif chunk_db.processing_started_at:
                    age = datetime.utcnow() - chunk_db.processing_started_at
                    if age > timedelta(minutes=2):
                        should_recover = True
                else:
                    # No timestamp but RUNNING - likely stuck
                    should_recover = True
                
                if should_recover:
                    # Check if chunk actually has audio file
                    # Load chunk from database to check file existence
                    chunk = ChunkRepository.get_by_book_chapter_index(
                        chunk_db.book_id, chunk_db.chapter_number, chunk_db.index
                    )
                    
                    if chunk and chunk.has_audio:
                        # Has audio - mark as completed
                        ChunkRepository.update_status(
                            chunk_db.book_id,
                            chunk_db.chapter_number,
                            chunk_db.index,
                            ChunkStatus.COMPLETED,
                            session=session
                        )
                        recovered += 1
                        logger.info(f"Recovered completed chunk {chunk_db.book_id}/{chunk_db.chapter_number}/{chunk_db.index}")
                    else:
                        # No audio - reset to PENDING
                        ChunkRepository.update_status(
                            chunk_db.book_id,
                            chunk_db.chapter_number,
                            chunk_db.index,
                            ChunkStatus.PENDING,
                            session=session
                        )
                        recovered += 1
                        logger.info(f"Recovered stuck chunk {chunk_db.book_id}/{chunk_db.chapter_number}/{chunk_db.index}")
            
            # Clear current chunk if it matches a recovered chunk
            if self._current_chunk_id:
                parts = self._current_chunk_id.split('_')
                if len(parts) >= 3:
                    try:
                        book_id = parts[0]
                        chapter_num = int(parts[1])
                        chunk_idx = int(parts[2])
                        # Check if this chunk was recovered using repository
                        recovered_chunk = ChunkRepository.get_chunk_for_recovery_check(
                            book_id, chapter_num, chunk_idx, session=session
                        )
                        if recovered_chunk and recovered_chunk.status != ChunkStatus.RUNNING.value:
                            self._current_chunk_id = None
                            self._processing = False
                            logger.info("Cleared current chunk after recovery")
                    except (ValueError, IndexError):
                        pass
        
        if recovered > 0:
            logger.info(f"✅ Recovered {recovered} stuck chunks")
        
        return recovered
    
    def get_queue_status(
        self,
        book_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        include_eta: bool = False,
    ) -> Dict[str, Any]:
        """
        Get current queue status with progress information from database.
        
        Args:
            book_id: Optional book ID to filter jobs
            chapter_number: Optional chapter number to filter jobs
            include_eta: If True, include estimated time remaining (expensive)
            
        Returns:
            Dictionary with queue statistics and progress
        """
        # Query database for counts
        # Recover stuck jobs if needed
        current_time = time.time()
        
        # If background processor is disabled, recover stuck jobs immediately
        # (they'll show as 0 running after recovery)
        if not self.settings.enable_background_processor:
            # Force recovery if processor is disabled (don't wait for interval)
            if current_time - self._last_recovery_time > 1.0:  # At least 1 second between recoveries
                self.recover_stuck_jobs()
                self._last_recovery_time = current_time
        else:
            # Only recover stuck jobs periodically (every 30 seconds) to avoid performance hit
            if current_time - self._last_recovery_time > self._recovery_interval:
                self.recover_stuck_jobs()
                self._last_recovery_time = current_time
        
        pending = ChunkRepository.count_by_status(book_id, chapter_number, ChunkStatus.PENDING)
        running = ChunkRepository.count_by_status(book_id, chapter_number, ChunkStatus.RUNNING)
        completed = ChunkRepository.count_by_status(book_id, chapter_number, ChunkStatus.COMPLETED)
        failed = ChunkRepository.count_by_status(book_id, chapter_number, ChunkStatus.FAILED)
        
        total = pending + running + completed + failed
        
        # Calculate progress percentage
        progress_percent = 0.0
        if total > 0:
            progress_percent = ((completed + failed) / total) * 100
        
        # Get current job details if processing (only if processor is enabled)
        current_job_dict = None
        if self.settings.enable_background_processor and self._current_chunk_id:
            parts = self._current_chunk_id.split('_')
            if len(parts) >= 3:
                try:
                    curr_book_id = parts[0]
                    curr_chapter_num = int(parts[1])
                    curr_chunk_idx = int(parts[2])
                    
                    matches_filter = (
                        (book_id is None or curr_book_id == book_id)
                        and (chapter_number is None or curr_chapter_num == chapter_number)
                    )
                    
                    if matches_filter:
                        chunk = ChunkRepository.get_by_book_chapter_index(
                            curr_book_id, curr_chapter_num, curr_chunk_idx
                        )
                        if chunk:
                            current_job = ChunkJob.from_chunk(
                                chunk,
                                chapter_number=curr_chapter_num,
                                status=JobStatus.RUNNING
                            )
                            current_job_dict = current_job.to_dict()
                except (ValueError, IndexError):
                    pass
        
        # Calculate estimated time remaining (only if requested - expensive operation)
        avg_time_per_chunk = 7.0  # Default fallback (seconds)
        avg_time_per_char = 0.03  # Default fallback (seconds per character, ~30ms per char)
        estimated_seconds_remaining = pending * avg_time_per_chunk
        
        if include_eta and pending > 0:
            # Use SQL-based ETA calculation (much faster)
            # Get all pending chunks for ETA calculation
            pending_chunks = ChunkRepository.get_pending_chunks_ordered(limit=1000)
            pending_jobs = [
                (chunk.book_id, chapter_num, chunk.index)
                for chunk, chapter_num in pending_chunks
            ]
            
            # Calculate ETA using SQL queries
            eta_result = ChunkRepository.calculate_eta(pending_jobs)
            estimated_seconds_remaining = eta_result['estimated_seconds_remaining']
            avg_time_per_chunk = eta_result['avg_time_per_chunk']
            avg_time_per_char = eta_result['avg_time_per_char']
        
        # is_processing is True if actively processing OR if there are running jobs
        # But only if the background processor is enabled
        is_processing = (
            self.settings.enable_background_processor 
            and (self._processing or running > 0)
        )
        
        result = {
            'total': total,
            'pending': pending,
            'running': running,
            'completed': completed,
            'failed': failed,
            'is_processing': is_processing,
            'progress_percent': round(progress_percent, 2),
            'current_job': current_job_dict,
        }
        
        # Only include ETA fields if requested (expensive to calculate)
        if include_eta:
            result['estimated_seconds_remaining'] = int(estimated_seconds_remaining)
            result['avg_time_per_chunk'] = round(avg_time_per_chunk, 2)
            result['avg_time_per_char'] = round(avg_time_per_char, 4)
        
        return result
    
    def get_queue(
        self, 
        status_filter: Optional[JobStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get jobs from database, optionally filtered by status with pagination.
        Delegates to get_queue_from_db for DB-based queries.
        
        Args:
            status_filter: Optional status to filter by
            limit: Optional limit on number of jobs to return (None = all)
            offset: Offset for pagination
            
        Returns:
            Tuple of (list of job dictionaries, total count)
        """
        # Use DB-based query for all statuses
        return self.get_queue_from_db(status_filter=status_filter, limit=limit, offset=offset)
    
    def get_queue_from_db(
        self, 
        status_filter: Optional[JobStatus] = None, 
        limit: Optional[int] = None, 
        offset: int = 0,
        max_per_chapter: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get jobs from database ordered by book/chapter/chunk, with pagination.
        Uses efficient SQL queries instead of loading all jobs into memory.
        
        Args:
            status_filter: Optional status to filter by ('pending' or 'failed')
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            max_per_chapter: Optional limit on jobs per chapter (for pending jobs)
            
        Returns:
            Tuple of (list of job dictionaries, total count)
        """
        # For pending jobs, use DB query ordered by book/chapter/chunk
        if status_filter == JobStatus.PENDING:
            # Get total count first
            total_count = ChunkRepository.count_by_status(status=ChunkStatus.PENDING)
            
            # Fetch enough chunks to cover offset + limit (with some buffer for max_per_chapter)
            fetch_limit = (limit or 500) + offset + (max_per_chapter or 0) * 10 if limit else None
            pending_chunks_with_numbers = ChunkRepository.get_pending_chunks_ordered(
                limit=fetch_limit or 1000
            )
            
            # Apply max_per_chapter limit if specified (group by chapter, keep first N)
            if max_per_chapter:
                chunks_by_chapter = {}
                for chunk, chapter_number in pending_chunks_with_numbers:
                    key = f"{chunk.book_id}_{chapter_number}"
                    if key not in chunks_by_chapter:
                        chunks_by_chapter[key] = []
                    if len(chunks_by_chapter[key]) < max_per_chapter:
                        chunks_by_chapter[key].append((chunk, chapter_number))
                # Flatten back to list, maintaining order
                pending_chunks_with_numbers = []
                for chapter_chunks in chunks_by_chapter.values():
                    pending_chunks_with_numbers.extend(chapter_chunks)
                # Re-sort to maintain book/chapter/chunk order
                pending_chunks_with_numbers.sort(key=lambda x: (x[0].book_id, x[1], x[0].index))
            
            # Convert to ChunkJob objects from chunk data
            jobs = [
                ChunkJob.from_chunk(chunk, chapter_number=chapter_number, status=JobStatus.PENDING)
                for chunk, chapter_number in pending_chunks_with_numbers
            ]
            
            # Apply pagination
            if limit is not None:
                jobs = jobs[offset:offset + limit]
            
            # Convert to dictionaries for API response
            return [job.to_dict() for job in jobs], total_count
        
        # For failed jobs, use repository
        elif status_filter == JobStatus.FAILED:
            # Use a session to ensure objects remain attached
            with db_session() as session:
                # Get total count first
                total_count = ChunkRepository.count_by_status(status=ChunkStatus.FAILED, session=session)
                
                # Get chunks using repository (pass session to keep objects attached)
                failed_chunks_db = ChunkRepository.get_chunks_by_status(
                    status=ChunkStatus.FAILED,
                    limit=limit,
                    offset=offset,
                    order_by_updated=False,
                    session=session
                )
                
                # Convert to ChunkJob objects from chunk data (while session is active)
                jobs = [
                    ChunkJob.from_chunk(chunk_db, status=JobStatus.FAILED)
                    for chunk_db in failed_chunks_db
                ]
                
                # Convert to dictionaries for API response
                return [job.to_dict() for job in jobs], total_count
        
        # For other statuses, use repository
        if status_filter:
            status_enum = ChunkStatus(status_filter.value) if hasattr(status_filter, 'value') else None
        else:
            status_enum = None
        
        if status_enum:
            # Use a session to ensure objects remain attached
            with db_session() as session:
                # Get total count first
                total_count = ChunkRepository.count_by_status(status=status_enum, session=session)
                
                # Get chunks using repository (pass session to keep objects attached)
                chunks_db = ChunkRepository.get_chunks_by_status(
                    status=status_enum,
                    limit=limit,
                    offset=offset,
                    order_by_updated=False,
                    session=session
                )
                
                # Convert to ChunkJob objects (while session is active)
                jobs = [
                    ChunkJob.from_chunk(chunk_db)
                    for chunk_db in chunks_db
                ]
                
                # Convert to dictionaries for API response
                return [job.to_dict() for job in jobs], total_count
        else:
            # No status filter - get all chunks (unlikely use case, but handle it)
            # This would require a new repository method, but for now return empty
            return [], 0
    
    def get_progress_details(self) -> Dict[str, Any]:
        """
        Get detailed progress information from database.
        
        Returns:
            Dictionary with detailed progress stats
        """
        status = self.get_queue_status()
        
        # Get recent completed/failed/pending jobs using repository
        # Recent completed (last 10, ordered by updated_at DESC)
        recent_completed_db = ChunkRepository.get_chunks_by_status(
            status=ChunkStatus.COMPLETED,
            limit=10,
            order_by_updated=True
        )
        
        recent_completed = [
            ChunkJob.from_chunk(c, status=JobStatus.COMPLETED).to_dict()
            for c in recent_completed_db
        ]
        
        # Recent failed (last 10, ordered by updated_at DESC)
        recent_failed_db = ChunkRepository.get_chunks_by_status(
            status=ChunkStatus.FAILED,
            limit=10,
            order_by_updated=True
        )
        
        recent_failed = [
            ChunkJob.from_chunk(c, status=JobStatus.FAILED).to_dict()
            for c in recent_failed_db
        ]
        
        # Next pending (first 10, ordered by book/chapter/index)
        next_pending_db = ChunkRepository.get_chunks_by_status(
            status=ChunkStatus.PENDING,
            limit=10,
            order_by_updated=False
        )
        
        next_pending = [
            ChunkJob.from_chunk(c, status=JobStatus.PENDING).to_dict()
            for c in next_pending_db
        ]
        
        return {
            **status,
            'recent_completed': recent_completed,
            'recent_failed': recent_failed,
            'next_pending': next_pending,
        }
    
    def clear_queue(self) -> None:
        """Reset all PENDING and RUNNING chunks to PENDING (effectively clearing queue)."""
        with db_session() as session:
            # Get all RUNNING chunks using repository
            running_chunks = ChunkRepository.get_running_chunks(session=session)
            
            # Reset all RUNNING chunks to PENDING
            for chunk_db in running_chunks:
                ChunkRepository.update_status(
                    chunk_db.book_id,
                    chunk_db.chapter_number,
                    chunk_db.index,
                    ChunkStatus.PENDING,
                    session=session
                )
            
            self._current_chunk_id = None
            self._processing = False
            logger.info(f"Cleared queue: reset {len(running_chunks)} RUNNING chunks to PENDING")
    
    async def process_next(self) -> Optional[ChunkJob]:
        """
        Process the next pending chunk from the database.
        
        Returns:
            The processed job, or None if no pending chunks
        """
        if self._processing:
            logger.debug("Already processing a job, skipping")
            return None
        
        # Query database for next pending or failed chunk in order
        # Get pending chunks and failed chunks (for retry)
        # We'll filter out already-retried failed chunks below
        chunks_with_numbers = ChunkRepository.get_pending_chunks_ordered(limit=10, include_failed=True)
        
        if not chunks_with_numbers:
            logger.debug("No pending or failed chunks in database")
            return None
        
        # Find first chunk that's either pending, or failed but not yet retried
        chunk = None
        chapter_number = None
        for candidate_chunk, candidate_chapter_number in chunks_with_numbers:
            chunk_id = f"{candidate_chunk.book_id}_{candidate_chapter_number}_{candidate_chunk.index}"
            
            if candidate_chunk.status == ChunkStatus.PENDING:
                # Pending chunk - process it
                chunk = candidate_chunk
                chapter_number = candidate_chapter_number
                break
            elif candidate_chunk.status == ChunkStatus.FAILED:
                # Failed chunk - check if we've already retried it
                if chunk_id not in self._retried_failed_chunks:
                    # Not retried yet - reset to PENDING and retry
                    logger.info(f"Retrying failed chunk {chunk_id} (first retry)")
                    ChunkRepository.update_status(
                        candidate_chunk.book_id,
                        candidate_chapter_number,
                        candidate_chunk.index,
                        ChunkStatus.PENDING,
                        error=None  # Clear error message
                    )
                    self._retried_failed_chunks.add(chunk_id)
                    chunk = candidate_chunk
                    chapter_number = candidate_chapter_number
                    # Update chunk status to PENDING in memory
                    chunk = Chunk(
                        index=candidate_chunk.index,
                        book_id=candidate_chunk.book_id,
                        text_start=candidate_chunk.text_start,
                        text_end=candidate_chunk.text_end,
                        status=ChunkStatus.PENDING,
                        chapter_id=candidate_chunk.chapter_id,
                        path=candidate_chunk.path,
                        generation_time_seconds=candidate_chunk.generation_time_seconds,
                        voice_name=candidate_chunk.voice_name,
                        speed=candidate_chunk.speed,
                        pre_pause_ms=candidate_chunk.pre_pause_ms,
                        post_pause_ms=candidate_chunk.post_pause_ms,
                        is_dialogue=candidate_chunk.is_dialogue,
                        is_scene_break=candidate_chunk.is_scene_break,
                    )
                    break
                # else: Already retried, skip and try next chunk
        
        if chunk is None:
            logger.debug("No chunks available (all pending chunks processed or all failed chunks already retried)")
            return None
        
        # Mark as RUNNING in database
        ChunkRepository.update_status(
            chunk.book_id,
            chapter_number,
            chunk.index,
            ChunkStatus.RUNNING,
            processing_started_at=datetime.utcnow()
        )
        
        # Create job object for processing (for compatibility with existing code)
        next_job = ChunkJob(
            book_id=chunk.book_id,
            chapter_number=chapter_number,
            chunk_index=chunk.index,
            speaker=chunk.voice_name,
            speed=chunk.speed,
            status=JobStatus.RUNNING,
            created_at=None,
        )
        
        self._processing = True
        self._current_chunk_id = f"{chunk.book_id}_{chapter_number}_{chunk.index}"
        
        # Emit job started event
        try:
            event_manager = get_event_manager()
            await event_manager.broadcast_job_started(next_job.to_dict())
            # Also broadcast status update
            status = self.get_queue_status(include_eta=True)
            await event_manager.broadcast_status_update(status)
        except Exception as e:
            logger.debug(f"Failed to emit job_started event: {e}")
        
        try:
            # Initialize TTS controller if needed
            if self._tts_controller is None:
                self._tts_controller = TTSController()
            
            logger.info(
                f"Processing chunk: {next_job.book_id}/{next_job.chapter_number}/chunk_{next_job.chunk_index}"
            )
            
            # Process the chunk (this is synchronous, so we run it in a thread)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._tts_controller.generate_chunk_audio,
                next_job.book_id,
                next_job.chapter_number,
                next_job.chunk_index,
                next_job.speaker,
                next_job.speed,
            )
            
            # Update DB status to COMPLETED
            ChunkRepository.update_status(
                next_job.book_id,
                chapter_number,
                chunk.index,
                ChunkStatus.COMPLETED,
                error=None
            )
            next_job.status = JobStatus.COMPLETED
            logger.info(f"✅ Completed chunk {next_job.chunk_index}")
            
            # Emit job completed event
            try:
                event_manager = get_event_manager()
                await event_manager.broadcast_job_completed(next_job.to_dict())
                # Also broadcast status update
                status = self.get_queue_status(include_eta=True)
                await event_manager.broadcast_status_update(status)
            except Exception as e:
                logger.debug(f"Failed to emit job_completed event: {e}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process chunk {next_job.chunk_index}: {error_msg}")
            
            # Update DB status to FAILED with error message
            ChunkRepository.update_status(
                next_job.book_id,
                chapter_number,
                chunk.index,
                ChunkStatus.FAILED,
                error=error_msg
            )
            next_job.status = JobStatus.FAILED
            next_job.error = error_msg
            
            # Emit job failed event
            try:
                event_manager = get_event_manager()
                await event_manager.broadcast_job_failed(next_job.to_dict())
                # Also broadcast status update
                status = self.get_queue_status(include_eta=True)
                await event_manager.broadcast_status_update(status)
            except Exception as e:
                logger.debug(f"Failed to emit job_failed event: {e}")
        
        finally:
            self._processing = False
            self._current_chunk_id = None
        
        return next_job
    
    async def process_all(self, callback: Optional[Callable[[ChunkJob, Dict[str, int], Dict[str, Any]], None]] = None) -> Dict[str, int]:
        """
        Process all pending jobs in the queue sequentially.
        
        Args:
            callback: Optional callback function called after each job (receives job, stats, and status)
        
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            'processed': 0,
            'completed': 0,
            'failed': 0,
        }
        
        while True:
            job = await self.process_next()
            if job is None:
                break
            
            stats['processed'] += 1
            if job.status == JobStatus.COMPLETED:
                stats['completed'] += 1
            elif job.status == JobStatus.FAILED:
                stats['failed'] += 1
            
            # Call callback if provided (for progress updates)
            if callback:
                try:
                    callback(job, stats, self.get_queue_status())
                except Exception as e:
                    logger.warning(f"Callback error: {e}")
        
        logger.info(
            f"✅ Processed {stats['processed']} jobs: "
            f"{stats['completed']} completed, {stats['failed']} failed"
        )
        return stats
    
    def start_background_processor(self, interval_seconds: float = 1.0) -> asyncio.Task:
        """
        Start a background task that processes jobs continuously.
        
        Args:
            interval_seconds: Seconds to wait between processing attempts
            
        Returns:
            asyncio.Task for the background processor
        """
        # Don't start if already running
        if self._processor_task and not self._processor_task.done():
            logger.debug("Background processor already running")
            return self._processor_task
        
        # Set up file logger for background processor
        processor_logger = self._get_processor_logger()
        
        async def _processor():
            processor_logger.info("=" * 80)
            processor_logger.info("Background processor started")
            processor_logger.info(f"Polling interval: {interval_seconds} seconds")
            processor_logger.info("=" * 80)
            
            # Reset retry tracking for this processor run
            # Failed chunks will be retried once, then skipped if they fail again
            self._retried_failed_chunks.clear()
            
            consecutive_empty_polls = 0
            while True:
                try:
                    job = await self.process_next()
                    if job is None:
                        consecutive_empty_polls += 1
                        # Log less frequently when idle (every 10 empty polls = ~10 seconds)
                        if consecutive_empty_polls % 10 == 0:
                            processor_logger.debug(f"No jobs to process (checked {consecutive_empty_polls} times)")
                    else:
                        consecutive_empty_polls = 0
                        processor_logger.info(
                            f"✅ Processed job: {job.book_id}/chapter_{job.chapter_number}/chunk_{job.chunk_index} "
                            f"(status: {job.status.value})"
                        )
                        if job.status == JobStatus.FAILED and job.error:
                            processor_logger.error(f"Job failed: {job.error[:200]}")
                except Exception as e:
                    processor_logger.error(f"Error in background processor: {e}", exc_info=True)
                    consecutive_empty_polls = 0
                
                await asyncio.sleep(interval_seconds)
        
        self._processor_task = asyncio.create_task(_processor())
        logger.info("✅ Started background processor task")
        processor_logger.info("Background processor task created")
        return self._processor_task
    
    def _get_processor_logger(self) -> logging.Logger:
        """Get or create a file logger for the background processor."""
        processor_logger_name = f"{__name__}.processor"
        processor_logger = logging.getLogger(processor_logger_name)
        
        # Only set up handler if not already configured
        if not processor_logger.handlers:
            # Create file handler for processor logs
            log_file = self.settings.log_dir / "queue_processor.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            processor_logger.addHandler(file_handler)
            processor_logger.setLevel(logging.DEBUG)
            # Prevent propagation to root logger (avoid duplicate logs)
            processor_logger.propagate = False
        
        return processor_logger


# Singleton queue instance
_queue_instance: Optional['ChunkJobQueue'] = None


def get_queue() -> 'ChunkJobQueue':
    """
    Get the singleton queue instance.
    
    Returns:
        ChunkJobQueue instance
    """
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = ChunkJobQueue()
    return _queue_instance

