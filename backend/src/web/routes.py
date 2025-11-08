"""API routes."""

from pathlib import Path
from typing import Optional

import attr
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.book_service import BookService
from src.services.chapter_service import ChapterService
from src.web.jobs import get_job_manager, JobType
from src.services.chunking_service import ChunkingService
from src.services.tts_service import TTSChunkService
from src.models.responses import (
    ChunkInfo,
    ChunkListResponse,
    OperationResult,
)


# Initialize job manager on module load
_ = get_job_manager()

router = APIRouter()


@router.get("/api/books")
async def list_books():
    """List all books."""
    service = BookService()
    books = service.discover_books()
    # Convert models to dicts for FastAPI JSON serialization
    return {"books": [attr.asdict(book) for book in books]}


@router.get("/api/books/preview")
async def get_book_preview(book_url: str, book_number: Optional[int] = None):
    """Get preview information for a book from Royal Road."""
    service = BookService()
    preview = service.get_book_preview(book_url, book_number)
    return attr.asdict(preview)


@router.get("/api/books/{book_id}")
async def get_book(book_id: str):
    """Get book details."""
    book_service = BookService()
    
    book_info = book_service.get_book_info(book_id)
    if not book_info:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return attr.asdict(book_info)


@router.get("/api/books/{book_id}/chapters")
async def list_chapters(book_id: str):
    """List chapters for a book."""
    service = ChapterService()
    chapters = service.discover_chapters(book_id)
    # discover_chapters still returns dicts for now (legacy format)
    return {"chapters": chapters}


# Put chunk routes BEFORE chapter_number route to avoid route matching conflicts
# FastAPI matches routes in order, so more specific routes must come first

@router.get("/api/books/{book_id}/chapters/{chapter_number}/chunks")
async def get_chunk_info(book_id: str, chapter_number: int):
    """Get chunk information including text mapping."""
    from src.controllers.chapter_controller import ChapterController
    from src.controllers.chunk_controller import ChunkController
    from src.utils.config import get_settings
    
    chapter_ctrl = ChapterController()
    chunk_ctrl = ChunkController()
    
    # Get chapter
    chapter = chapter_ctrl.get_chapter(book_id, chapter_number)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get chapter text
    text_content = chapter_ctrl.get_chapter_text(book_id, chapter_number) or ""
    
    # Get chunks
    chunks = chapter_ctrl.get_chunks(book_id, chapter_number)
    
    # Build chunks info
    chunks_info = []
    settings = get_settings()
    
    for chunk in chunks:
        # Get audio URL if exists
        audio_url = None
        if chunk.has_audio and chunk.audio_path:
            rel_path = chunk.audio_path.relative_to(settings.books_dir)
            audio_url = f"/audio/{rel_path.as_posix()}"
        
        chunk_info = {
            'index': chunk.index,
            'filename': chunk.audio_path.name if chunk.audio_path else None,
            'path': str(chunk.audio_path) if chunk.audio_path else None,
            'url': audio_url,
            'flagged': chunk.is_flagged,
            'text_start': chunk.text_start,
            'text_end': chunk.text_end,
            'text_length': chunk.text_length,
            'status': chunk.status.value,
            'generation_time_seconds': chunk.generation_time_seconds,
        }
        chunks_info.append(chunk_info)
    
    # Sort chunks by index
    chunks_info.sort(key=lambda x: x['index'])
    
    # Get flagged chunks
    flagged_chunks = [ch.index for ch in chunks if ch.is_flagged]
    
    return {
        'chapter_number': chapter_number,
        'chapter_title': chapter.title,
        'text_file': str(chapter.text_path) if chapter.text_path else None,
        'text_length': len(text_content),
        'chunks': chunks_info,
        'flagged_chunks': flagged_chunks,
    }


@router.get("/api/books/{book_id}/chapters/{chapter_number}")
async def get_chapter(book_id: str, chapter_number: int):
    """Get chapter details."""
    from src.controllers.chapter_controller import ChapterController
    
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


# Job management routes

class ScrapeBookRequest(BaseModel):
    book_url: str
    filter_book_number: Optional[int] = None


class GenerateAudioRequest(BaseModel):
    book_id: str
    chapter_number: Optional[int] = None
    speaker: Optional[str] = None


class GenerateChunkRequest(BaseModel):
    book_id: str
    chapter_number: int
    chunk_index: int
    speaker: Optional[str] = None


class DownloadBookRequest(BaseModel):
    book_url: str
    filter_book_number: Optional[int] = None
    max_chapters: Optional[int] = None


class DownloadChapterRequest(BaseModel):
    book_id: str
    chapter_url: str
    chapter_number: Optional[int] = None


class ChunkChapterRequest(BaseModel):
    book_id: str
    chapter_number: int
    chunk_duration_minutes: Optional[float] = 1.0
    target_chars: Optional[int] = None
    min_chars: Optional[int] = None
    max_chars: Optional[int] = None


class GenerateChunksRequest(BaseModel):
    book_id: str
    chapter_number: int
    chunk_indices: Optional[list[int]] = None
    speaker: Optional[str] = None
    language: Optional[str] = None
    speed: Optional[float] = None
    emotion: Optional[str] = None


@router.get("/api/books/{book_id}/series")
async def get_series_books(book_id: str):
    """Get other books in the same series."""
    service = BookService()
    series_books = service.find_series_books(book_id)
    return {"books": series_books}


@router.post("/api/jobs/scrape")
async def create_scrape_job(request: ScrapeBookRequest):
    """Create a book scraping job."""
    job_manager = get_job_manager()
    job_id = job_manager.create_job(
        JobType.SCRAPE_BOOK,
        book_url=request.book_url,
        filter_book_number=request.filter_book_number,
    )
    return {"job_id": job_id}


@router.post("/api/jobs/generate-audio")
async def create_generate_audio_job(request: GenerateAudioRequest):
    """Create an audio generation job."""
    job_manager = get_job_manager()
    
    if request.chapter_number:
        job_id = job_manager.create_job(
            JobType.GENERATE_CHAPTER_AUDIO,
            book_id=request.book_id,
            chapter_number=request.chapter_number,
            speaker=request.speaker,
        )
    else:
        job_id = job_manager.create_job(
            JobType.GENERATE_AUDIO,
            book_id=request.book_id,
            speaker=request.speaker,
        )
    
    return {"job_id": job_id}


@router.post("/api/jobs/generate-chunk")
async def create_generate_chunk_job(request: GenerateChunkRequest):
    """Create a job to generate a specific chunk."""
    job_manager = get_job_manager()
    
    job_id = job_manager.create_job(
        JobType.GENERATE_CHUNK_AUDIO,
        book_id=request.book_id,
        chapter_number=request.chapter_number,
        chunk_index=request.chunk_index,
        speaker=request.speaker,
    )
    
    return {"job_id": job_id}


@router.get("/api/jobs")
async def list_jobs(book_id: Optional[str] = None):
    """List all jobs, optionally filtered by book_id."""
    job_manager = get_job_manager()
    jobs = job_manager.list_jobs(book_id=book_id)
    return {"jobs": jobs}


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job details."""
    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    job_manager = get_job_manager()
    success = job_manager.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"status": "cancelled"}


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
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
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
    language: Optional[str] = None,
    speed: Optional[float] = None,
    emotion: Optional[str] = None,
):
    """Generate TTS audio for a single chunk."""
    service = TTSChunkService()
    try:
        result = service.generate_chunk_audio(
            book_id=book_id,
            chapter_number=chapter_number,
            chunk_index=chunk_index,
            speaker=speaker,
            language=language,
            speed=speed,
            emotion=emotion,
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
            language=request.language,
            speed=request.speed,
            emotion=request.emotion,
        )
        return attr.asdict(OperationResult(
            status="success",
            result=attr.asdict(result) if hasattr(result, '__attrs_attrs__') else result,
        ))
    except Exception as e:
        return attr.asdict(OperationResult(status="error", error=str(e)))


# Chunk management routes

@router.post("/api/books/{book_id}/chapters/{chapter_number}/chunks/{chunk_index}/flag")
async def flag_chunk(book_id: str, chapter_number: int, chunk_index: int):
    """Flag a chunk for reprocessing."""
    from src.controllers.chunk_controller import ChunkController
    
    chunk_ctrl = ChunkController()
    
    # Flag the chunk
    chunk = chunk_ctrl.flag_chunk(book_id, chapter_number, chunk_index, flagged=True)
    
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    return {
        "status": "flagged",
        "book_id": book_id,
        "chapter_number": chapter_number,
        "chunk_index": chunk_index,
    }


@router.get("/api/search")
async def search_books(query: str):
    """Search Royal Road for books."""
    try:
        service = BookService()
        results = service.search_royal_road(query)
        return {"books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

