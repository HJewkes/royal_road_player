"""API routes."""

import logging
from pathlib import Path
from typing import Optional

import attr
from fastapi import APIRouter, HTTPException

from src.controllers.chapter_controller import ChapterController

logger = logging.getLogger(__name__)
from src.controllers.chunk_controller import ChunkController
from src.services.book_service import BookService
from src.services.chapter_service import ChapterService
from src.services.chunking_service import ChunkingService
from src.services.tts_service import TTSChunkService
from src.services.job_queue import ChunkJobQueue, get_queue
from src.services.audio_concatenator import AudioConcatenator
from src.models.responses import (
    ChunkInfo,
    ChunkListResponse,
    OperationResult,
)
from src.utils.config import get_settings
from src.web.models import (
    DownloadBookRequest,
    DownloadChapterRequest,
    ChunkChapterRequest,
    GenerateChunksRequest,
    QueueChunksRequest,
)

router = APIRouter()


@router.get("/api/books")
async def list_books(lightweight: bool = True):
    """
    List all books.
    
    Args:
        lightweight: If True, use fast metadata-only stats computation
    """
    service = BookService()
    books = service.discover_books(lightweight=lightweight)
    # Convert models to dicts for FastAPI JSON serialization
    return {"books": [attr.asdict(book) for book in books]}


@router.get("/api/books/preview")
async def get_book_preview(book_url: str, book_number: Optional[int] = None):
    """Get preview information for a book from Royal Road."""
    service = BookService()
    preview = service.get_book_preview(book_url, book_number)
    return attr.asdict(preview)


@router.get("/api/books/{book_id}")
async def get_book(
    book_id: str, 
    include_chapters: bool = False, 
    lightweight: bool = True,
    include_stats: bool = True,
):
    """
    Get book details.
    
    Args:
        book_id: Book identifier
        include_chapters: If True, include chapter list in response (combines two API calls)
        lightweight: If True, use fast metadata-only stats computation
        include_stats: If False, skip expensive stats calculation (for faster initial load)
    """
    book_service = BookService()
    
    book_info = book_service.get_book_info(book_id, lightweight=lightweight, include_stats=include_stats)
    if not book_info:
        raise HTTPException(status_code=404, detail="Book not found")
    
    result = attr.asdict(book_info)
    
    # If include_chapters is requested, add full chapter details
    if include_chapters:
        chapter_service = ChapterService()
        chapters = chapter_service.discover_chapters(book_id, lightweight=lightweight, include_audio_urls=False)
        result["chapters"] = chapters
    
    return result


@router.get("/api/books/{book_id}/chapters")
async def list_chapters(book_id: str, lightweight: bool = True, include_audio_urls: bool = False):
    """
    List chapters for a book.
    
    Args:
        book_id: Book identifier
        lightweight: If True, use fast metadata-only stats computation
        include_audio_urls: If True, include audio URLs (slower, scans filesystem)
    """
    service = ChapterService()
    chapters = service.discover_chapters(book_id, lightweight=lightweight, include_audio_urls=include_audio_urls)
    # discover_chapters still returns dicts for now (legacy format)
    return {"chapters": chapters}


# Put chunk routes BEFORE chapter_number route to avoid route matching conflicts
# FastAPI matches routes in order, so more specific routes must come first

@router.get("/api/books/{book_id}/chapters/{chapter_number}/chunks/{chunk_index}/text")
async def get_chunk_text(book_id: str, chapter_number: int, chunk_index: int):
    """Get text content for a specific chunk."""
    chunk_ctrl = ChunkController()
    chunk = chunk_ctrl.get_chunk(book_id, chapter_number, chunk_index)
    
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    if not chunk.has_text or chunk.text_path is None or not chunk.text_path.exists():
        raise HTTPException(status_code=404, detail="Chunk text not found")
    
    try:
        text_content = chunk.text_path.read_text(encoding='utf-8')
        return {"text": text_content, "chunk_index": chunk_index}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read chunk text: {str(e)}")


@router.get("/api/books/{book_id}/chapters/{chapter_number}/chunks")
async def get_chunk_info(book_id: str, chapter_number: int, include_text: bool = False):
    """
    Get chunk information including text mapping and audio timing.
    
    Args:
        book_id: Book identifier
        chapter_number: Chapter number
        include_text: If True, include chunk text content (default: False for performance)
    """
    chapter_ctrl = ChapterController()
    chunk_ctrl = ChunkController()
    
    # Get chapter
    chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get chapter text (only if we need text_length)
    text_content = ""
    if include_text:
        text_content = chapter_ctrl.get_chapter_text(book_id, chapter_number) or ""
    
    # Get chunks (sorted by index)
    chunks = sorted(chapter_ctrl.get_chunks(book_id, chapter_number), key=lambda x: x.index)
    
    # Calculate cumulative start/end times for chunks with audio
    cumulative_time = 0.0
    chunks_info = []
    settings = get_settings()
    
    # Import wave for reading durations (only if needed)
    import wave
    
    for chunk in chunks:
        # Get audio URL if exists
        audio_url = None
        if chunk.has_audio and chunk.audio_path:
            rel_path = chunk.audio_path.relative_to(settings.books_dir)
            audio_url = f"/audio/{rel_path.as_posix()}"
        
        # Read text content only if requested (expensive operation)
        chunk_text = None
        if include_text and chunk.text_path and chunk.text_path.exists():
            try:
                chunk_text = chunk.text_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to read text file for chunk {chunk.index}: {e}")
                chunk_text = None
        
        # Get audio duration from metadata (prefer metadata, avoid reading WAV files)
        audio_duration = chunk.audio_duration_seconds
        # Only read from WAV file if duration is missing AND chunk has audio
        # This is expensive, so we skip it if metadata has duration
        if (not audio_duration or audio_duration <= 0) and chunk.has_audio and chunk.audio_path and chunk.audio_path.exists():
            try:
                with wave.open(str(chunk.audio_path), 'rb') as wav_file:
                    n_frames = wav_file.getnframes()
                    framerate = wav_file.getframerate()
                    audio_duration = n_frames / framerate if framerate > 0 else None
            except Exception as e:
                logger.debug(f"Failed to read audio duration from file for chunk {chunk.index}: {e}")
                audio_duration = None
        
        # Calculate audio start/end times (only for chunks with audio and valid duration)
        audio_start_time = None
        audio_end_time = None
        if chunk.has_audio and audio_duration is not None and audio_duration > 0:
            audio_start_time = cumulative_time
            audio_end_time = cumulative_time + audio_duration
            cumulative_time = audio_end_time
        
        chunk_info = {
            'index': chunk.index,
            'filename': chunk.audio_path.name if chunk.audio_path else None,
            'path': str(chunk.audio_path) if chunk.audio_path else None,
            'url': audio_url,
            'text_start': chunk.text_start,
            'text_end': chunk.text_end,
            'text_length': chunk.text_length,
            'status': chunk.status.value,
            'generation_time_seconds': chunk.generation_time_seconds,
            'audio_duration_seconds': audio_duration,  # Use calculated duration (from metadata or file)
            'audio_start_time': audio_start_time,  # Start time in seconds (cumulative)
            'audio_end_time': audio_end_time,  # End time in seconds (cumulative)
        }
        
        # Only include text if requested (saves significant bandwidth)
        if include_text:
            chunk_info['text'] = chunk_text
        
        chunks_info.append(chunk_info)
    
    result = {
        'chapter_number': chapter_number,
        'chapter_title': chapter.title,
        'text_file': str(chapter.text_path) if chapter.text_path else None,
        'text_length': len(text_content) if include_text else (chunks[-1].text_end if chunks else 0),
        'chunks': chunks_info,
        'total_audio_duration': cumulative_time,  # Total duration of all chunks with audio
    }
    
    return result


@router.get("/api/books/{book_id}/chapters/{chapter_number}")
async def get_chapter(book_id: str, chapter_number: int):
    """Get chapter details."""
    chapter_ctrl = ChapterController()
    chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get audio URLs
    chapter_service = ChapterService()
    audio_urls = chapter_service.get_chapter_audio_urls(book_id, chapter_number)
    
    # Get chapter info using service (which returns ChapterInfo model)
    chapter_service = ChapterService()
    chapter_info = chapter_service.get_chapter_info(book_id, chapter_number)
    
    if not chapter_info:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return attr.asdict(chapter_info)


@router.post("/api/books/{book_id}/chapters/{chapter_number}/concatenate")
async def concatenate_chapter_audio(book_id: str, chapter_number: int):
    """Generate concatenated audio file from all chunks."""
    concatenator = AudioConcatenator()
    settings = get_settings()
    
    try:
        audio_path = concatenator.get_concatenated_audio_path(book_id, chapter_number)
        
        if audio_path is None:
            raise HTTPException(
                status_code=404,
                detail="No audio chunks found or concatenation failed"
            )
        
        # Convert to URL relative to /audio mount
        rel_path = audio_path.relative_to(settings.books_dir)
        audio_url = f"/audio/{rel_path.as_posix()}"
        
        return {
            "status": "success",
            "audio_url": audio_url,
            "audio_path": str(audio_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to concatenate audio: {str(e)}")


@router.get("/api/books/{book_id}/series")
async def get_series_books(book_id: str):
    """Get other books in the same series."""
    service = BookService()
    series_books = service.find_series_books(book_id)
    return {"books": series_books}


# Service-based workflow endpoints

@router.post("/api/books/download")
async def download_book(request: DownloadBookRequest):
    """Download a book's text (all chapters)."""
    service = BookService()
    try:
        result = service.download_book(
            book_url=request.book_url,
            filter_book_number=request.filter_book_number,
            max_chapters=request.max_chapters,
        )
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/chapters/download")
async def download_chapter(request: DownloadChapterRequest):
    """Download a single chapter's text."""
    service = ChapterService()
    try:
        result = service.download_chapter(
            book_id=request.book_id,
            chapter_url=request.chapter_url,
            chapter_number=request.chapter_number,
        )
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/chapters/chunk")
async def chunk_chapter(request: ChunkChapterRequest):
    """Chunk a chapter's text into segments."""
    service = ChunkingService()
    try:
        result = service.chunk_chapter(
            book_id=request.book_id,
            chapter_number=request.chapter_number,
            chunk_duration_minutes=request.chunk_duration_minutes or 1.0,
            target_chars=request.target_chars,
            min_chars=request.min_chars,
            max_chars=request.max_chars,
        )
        # Convert result to dict for JSON serialization
        result_dict = attr.asdict(result)
        # Convert chunks to dicts
        result_dict['chunks'] = [attr.asdict(chunk) for chunk in result.chunks]
        return attr.asdict(OperationResult(
            status="success",
            result=result_dict,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/chapters/rechunk")
async def rechunk_chapter(request: ChunkChapterRequest):
    """Rechunk a chapter by clearing old chunks/audio and creating new ones."""
    service = ChunkingService()
    try:
        result = service.rechunk_chapter(
            book_id=request.book_id,
            chapter_number=request.chapter_number,
            chunk_duration_minutes=request.chunk_duration_minutes or 1.0,
            target_chars=request.target_chars,
            min_chars=request.min_chars,
            max_chars=request.max_chars,
        )
        # Convert result to dict for JSON serialization
        result_dict = attr.asdict(result)
        # Convert chunks to dicts
        result_dict['chunks'] = [attr.asdict(chunk) for chunk in result.chunks]
        return attr.asdict(OperationResult(
            status="success",
            result=result_dict,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.delete("/api/books/{book_id}/chapters/{chapter_number}/chunks")
async def clear_chunks(book_id: str, chapter_number: int):
    """Clear all chunks and audio files for a chapter."""
    service = ChunkingService()
    try:
        service.clear_chunks_and_audio(book_id, chapter_number)
        return attr.asdict(OperationResult(
            status="success",
            result={"message": f"Cleared chunks and audio for chapter {chapter_number}"},
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/books/{book_id}/chapters/{chapter_number}/chunks/cleanup")
async def cleanup_small_failed_chunks(
    book_id: str,
    chapter_number: int,
):
    """
    Clean up failed chunks that are purely whitespace.
    
    This deletes failed chunks that contain only whitespace characters.
    Useful for cleaning up chunks created before filtering logic was added.
    """
    service = ChunkingService()
    try:
        deleted_count = service.cleanup_small_failed_chunks(book_id, chapter_number)
        return attr.asdict(OperationResult(
            status="success",
            result={
                "message": f"Cleaned up {deleted_count} pure whitespace failed chunks",
                "deleted_count": deleted_count,
            },
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/books/{book_id}/chapters/{chapter_number}/chunks/backfill-durations")
async def backfill_chunk_durations(
    book_id: str,
    chapter_number: int,
):
    """
    Backfill audio_duration_seconds for existing chunks by reading from audio files.
    
    This reads durations from existing WAV files and updates chunk metadata without
    regenerating audio. Only updates chunks that have audio files but missing durations.
    """
    service = ChunkingService()
    try:
        stats = service.backfill_chunk_durations(book_id, chapter_number)
        return attr.asdict(OperationResult(
            status="success",
            result={
                "message": (
                    f"Backfilled durations: {stats['chunks_updated']} updated, "
                    f"{stats['chunks_already_had_duration']} already had duration, "
                    f"{stats['chunks_missing_audio']} missing audio, "
                    f"{stats['errors']} errors"
                ),
                **stats,
            },
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


# Note: Specific route must come before generic route
@router.post("/api/chunks/{chunk_index}/generate")
async def generate_single_chunk(
    book_id: str,
    chapter_number: int,
    chunk_index: int,
    speaker: Optional[str] = None,
    speed: Optional[float] = None,
):
    """Generate TTS audio for a single chunk."""
    service = TTSChunkService()
    try:
        result = service.generate_chunk_audio(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_index=chunk_index,
            speaker=speaker,
            speed=speed,
        )
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/chunks/generate")
async def generate_chunks(request: GenerateChunksRequest):
    """Generate TTS audio for one or more chunks."""
    service = TTSChunkService()
    try:
        result = service.generate_chapter_chunks(
            book_id=request.book_id,
            chapter_number=request.chapter_number,
            chunk_indices=request.chunk_indices,
            speaker=request.speaker,
            speed=request.speed,
        )
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.get("/api/search")
async def search_books(query: str):
    """Search Royal Road for books."""
    try:
        service = BookService()
        results = service.search_royal_road(query)
        return {"books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# Job queue endpoints

@router.post("/api/queue/chunks")
async def queue_chunks(request: QueueChunksRequest):
    """Queue chunks for sequential processing."""
    queue = get_queue()
    try:
        added = queue.enqueue_chapter_chunks(
            book_id=request.book_id,
            chapter_number=request.chapter_number,
            chunk_indices=request.chunk_indices,
            speaker=request.speaker,
            speed=request.speed,
        )
        return attr.asdict(OperationResult(
            status="success",
            result={"jobs_added": added, "queue_status": queue.get_queue_status()},
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.get("/api/queue/status")
async def get_queue_status(
    book_id: Optional[str] = None,
    chapter_number: Optional[int] = None,
    include_eta: bool = False,
):
    """
    Get current queue status, optionally filtered by book/chapter.
    
    Args:
        book_id: Optional book ID to filter jobs
        chapter_number: Optional chapter number to filter jobs
        include_eta: If True, include estimated time remaining (expensive, loads chunks)
    """
    queue = get_queue()
    return queue.get_queue_status(book_id=book_id, chapter_number=chapter_number, include_eta=include_eta)


@router.get("/api/queue/progress")
async def get_queue_progress():
    """Get detailed progress information including recent jobs."""
    queue = get_queue()
    return queue.get_progress_details()


@router.get("/api/queue/jobs")
async def get_queue_jobs(
    status: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: int = 0,
    use_db: bool = True,
    max_per_chapter: Optional[int] = None,
):
    """
    Get jobs in the queue with pagination, optionally filtered by status.
    Uses database queries for efficient ordered fetching when use_db=True.
    
    Args:
        status: Optional status filter ('pending', 'running', 'completed', 'failed')
        limit: Number of jobs to return (default: 50, max: 500)
        offset: Offset for pagination
        use_db: If True, use DB queries for ordered fetching (default: True)
        max_per_chapter: Optional limit on jobs per chapter (for pending jobs)
    """
    queue = get_queue()
    from src.services.job_queue import JobStatus
    
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            pass  # Invalid status, return all
    
    # Cap limit to prevent excessive data transfer
    if limit is not None:
        limit = min(limit, 500)
    
    # Use DB-based fetching for pending/failed jobs if requested
    if use_db and status_filter in (JobStatus.PENDING, JobStatus.FAILED):
        jobs, total = queue.get_queue_from_db(
            status_filter=status_filter, 
            limit=limit, 
            offset=offset,
            max_per_chapter=max_per_chapter
        )
    else:
        # Fall back to in-memory queue for other statuses
        jobs, total = queue.get_queue(status_filter=status_filter, limit=limit, offset=offset)
    
    return {
        "jobs": jobs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/queue/process")
async def process_queue():
    """Process all pending jobs in the queue sequentially."""
    import logging
    logger = logging.getLogger(__name__)
    queue = get_queue()
    try:
        # Reset any failed jobs to PENDING so they can be retried
        # Note: Background processor is already running (started on app startup)
        from src.services.job_queue import JobStatus
        reset_count = 0
        total_jobs = len(queue._queue)
        failed_before = sum(1 for j in queue._queue if j.status == JobStatus.FAILED)
        logger.info(f"Queue has {total_jobs} total jobs, {failed_before} failed before reset")
        
        for job in queue._queue:
            if job.status == JobStatus.FAILED:
                logger.info(f"Resetting job {job.chunk_index} (book={job.book_id}, chapter={job.chapter_number}) from FAILED to PENDING")
                job.status = JobStatus.PENDING
                reset_count += 1
        
        if reset_count > 0:
            logger.info(f"✅ Reset {reset_count} failed jobs to PENDING")
            queue._save_queue()
            # Verify save worked
            failed_after = sum(1 for j in queue._queue if j.status == JobStatus.FAILED)
            logger.info(f"After reset: {failed_after} failed jobs remaining (should be 0)")
        else:
            logger.info(f"No failed jobs to reset (found {failed_before} failed jobs but none matched)")
        
        # Background processor is already running (started on app startup)
        # Trigger immediate processing (processor will pick up jobs automatically)
        stats = await queue.process_all()
        return attr.asdict(OperationResult(
            status="success",
            result={
                **stats,
                "reset_failed_jobs": reset_count,
            },
        ))
    except Exception as e:
        logger.error(f"Error processing queue: {e}", exc_info=True)
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.post("/api/queue/process/next")
async def process_next_job():
    """Process the next job in the queue."""
    queue = get_queue()
    try:
        job = await queue.process_next()
        if job is None:
            return attr.asdict(OperationResult(
                status="success",
                result={"message": "No jobs to process"},
            ))
        return attr.asdict(OperationResult(
            status="success",
            result={"job": job.to_dict()},
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


@router.delete("/api/queue")
async def clear_queue():
    """Clear all jobs from the queue."""
    queue = get_queue()
    try:
        queue.clear_queue()
        return attr.asdict(OperationResult(
            status="success",
            result={"message": "Queue cleared"},
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))

