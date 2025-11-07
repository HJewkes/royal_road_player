"""API routes."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.web.database import get_db
from src.web.models import Book, Chapter, Progress
from src.web.book_discovery import discover_books, discover_chapters, get_chapter_audio_urls, find_series_books
from src.web.jobs import get_job_manager, JobType

# Import search function
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.find_book import search_royal_road

# Initialize job manager on module load
_ = get_job_manager()

router = APIRouter()


@router.get("/api/books")
async def list_books():
    """List all books."""
    books = discover_books()
    return {"books": books}


@router.get("/api/books/preview")
async def get_book_preview(book_url: str, book_number: Optional[int] = None):
    """Get preview information for a book from Royal Road."""
    from src.web.book_discovery import fetch_book_preview
    
    preview = fetch_book_preview(book_url, book_number)
    return preview


@router.get("/api/books/{book_id}")
async def get_book(book_id: str):
    """Get book details."""
    books = discover_books()
    book = next((b for b in books if b['id'] == book_id), None)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Get chapters
    chapters = discover_chapters(book_id)
    book['chapters'] = chapters
    
    return book


@router.get("/api/books/{book_id}/chapters")
async def list_chapters(book_id: str):
    """List chapters for a book."""
    chapters = discover_chapters(book_id)
    return {"chapters": chapters}


# Put chunk routes BEFORE chapter_number route to avoid route matching conflicts
# FastAPI matches routes in order, so more specific routes must come first

@router.get("/api/books/{book_id}/chapters/{chapter_title}/chunks")
async def get_chunk_info(book_id: str, chapter_title: str):
    """Get chunk information including text mapping."""
    from src.utils.metadata_tracker import MetadataTracker
    from src.utils.config import get_settings
    from pathlib import Path
    from urllib.parse import unquote
    
    # Decode URL-encoded chapter title
    chapter_title = unquote(chapter_title)
    
    settings = get_settings()
    
    # Find book directory
    book_dir = None
    for dir_path in settings.books_dir.iterdir():
        if dir_path.is_dir() and book_id in dir_path.name:
            metadata_path = dir_path / "metadata.json"
            if metadata_path.exists():
                import json
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        book_dir = dir_path
                        break
                except Exception:
                    continue
    
    if not book_dir:
        raise HTTPException(status_code=404, detail="Book not found")
    
    chapters_dir = book_dir / "chapters"
    chunk_files = sorted(chapters_dir.glob(f"{chapter_title}_chunk_*.wav"))
    
    # Get text file
    text_file = chapters_dir / f"{chapter_title}.txt"
    text_content = ""
    if text_file.exists():
        try:
            text_content = text_file.read_text(encoding='utf-8')
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to read text file {text_file}: {e}")
    
    # Get metadata
    tracker = MetadataTracker(book_dir)
    metadata = tracker.load()
    chapter_meta = next(
        (ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title),
        {}
    )
    
    # Get chunk metadata from chapter metadata
    chunk_metadata_list = chapter_meta.get('chunk_metadata', [])
    chunk_metadata_dict = {ch['index']: ch for ch in chunk_metadata_list}
    
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Chapter '{chapter_title}': found {len(chunk_metadata_list)} metadata entries, {len(chunk_files)} chunk files")
    if chunk_metadata_list:
        logger.debug(f"First metadata entry: {chunk_metadata_list[0]}")
    
    # Map chunks to text segments with positions
    chunks_info = []
    for chunk_file in chunk_files:
        # Extract chunk number from filename
        chunk_num_str = chunk_file.stem.rsplit('_chunk_', 1)[-1]
        try:
            chunk_index = int(chunk_num_str)
        except ValueError:
            continue
        
        # Get metadata for this chunk
        meta = chunk_metadata_dict.get(chunk_index, {})
        
        chunk_info = {
            'index': chunk_index,
            'filename': chunk_file.name,
            'path': str(chunk_file),
            'flagged': chunk_index in chapter_meta.get('flagged_chunks', []),
            'text_start': meta.get('text_start', 0),
            'text_end': meta.get('text_end', 0),
            'text_length': meta.get('text_length', 0),
            'status': meta.get('status', 'completed'),
            'generation_time_seconds': meta.get('generation_time_seconds'),
        }
        chunks_info.append(chunk_info)
    
    # Sort chunks by index
    chunks_info.sort(key=lambda x: x['index'])
    
    # Calculate total text length
    total_text_length = len(text_content) if text_content else 0
    
    return {
        'chapter_title': chapter_title,
        'text_file': str(text_file) if text_file.exists() else None,
        'text_length': total_text_length,
        'chunks': chunks_info,
        'flagged_chunks': chapter_meta.get('flagged_chunks', []),
    }


@router.get("/api/books/{book_id}/chapters/{chapter_number}")
async def get_chapter(book_id: str, chapter_number: int):
    """Get chapter details."""
    chapters = discover_chapters(book_id)
    chapter = next((c for c in chapters if c['chapter_number'] == chapter_number), None)
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get audio URLs
    chapter_title = Path(chapter['text_path']).stem
    audio_urls = get_chapter_audio_urls(book_id, chapter_title)
    chapter['audio_urls'] = audio_urls
    
    return chapter


@router.get("/api/progress/{book_id}")
async def get_progress(book_id: str, db: Session = Depends(get_db)):
    """Get playback progress for a book."""
    progress = db.query(Progress).filter(Progress.book_id == book_id).first()
    
    if not progress:
        return {
            "book_id": book_id,
            "current_chapter": 1,
            "position_seconds": 0.0,
            "completed": False,
        }
    
    return {
        "book_id": progress.book_id,
        "current_chapter": progress.chapter_id,
        "position_seconds": progress.position_seconds,
        "completed": bool(progress.completed),
    }


@router.post("/api/progress")
async def update_progress(
    book_id: str,
    chapter_id: int,
    position_seconds: float,
    completed: bool = False,
    db: Session = Depends(get_db),
):
    """Update playback progress."""
    progress = db.query(Progress).filter(
        Progress.book_id == book_id,
        Progress.chapter_id == chapter_id,
    ).first()
    
    if progress:
        progress.position_seconds = position_seconds
        progress.completed = 1 if completed else 0
    else:
        progress = Progress(
            book_id=book_id,
            chapter_id=chapter_id,
            position_seconds=position_seconds,
            completed=1 if completed else 0,
        )
        db.add(progress)
    
    db.commit()
    db.refresh(progress)
    
    return {
        "book_id": progress.book_id,
        "chapter_id": progress.chapter_id,
        "position_seconds": progress.position_seconds,
        "completed": bool(progress.completed),
    }


# Job management routes

class ScrapeBookRequest(BaseModel):
    book_url: str
    filter_book_number: Optional[int] = None


class GenerateAudioRequest(BaseModel):
    book_id: str
    chapter_title: Optional[str] = None
    speaker: Optional[str] = None


class GenerateChunkRequest(BaseModel):
    book_id: str
    chapter_title: str
    chunk_index: int
    speaker: Optional[str] = None


@router.get("/api/books/{book_id}/series")
async def get_series_books(book_id: str):
    """Get other books in the same series."""
    series_books = find_series_books(book_id)
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
    
    if request.chapter_title:
        job_id = job_manager.create_job(
            JobType.GENERATE_CHAPTER_AUDIO,
            book_id=request.book_id,
            chapter_title=request.chapter_title,
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
        chapter_title=request.chapter_title,
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


# Chunk management routes

@router.post("/api/books/{book_id}/chapters/{chapter_title}/chunks/{chunk_index}/flag")
async def flag_chunk(book_id: str, chapter_title: str, chunk_index: int):
    """Flag a chunk for reprocessing."""
    from src.utils.metadata_tracker import MetadataTracker
    from src.utils.config import get_settings
    from urllib.parse import unquote
    
    # Decode URL-encoded chapter title
    chapter_title = unquote(chapter_title)
    
    settings = get_settings()
    
    # Find book directory
    book_dir = None
    for dir_path in settings.books_dir.iterdir():
        if dir_path.is_dir() and book_id in dir_path.name:
            metadata_path = dir_path / "metadata.json"
            if metadata_path.exists():
                import json
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    if metadata.get('book_id') == book_id:
                        book_dir = dir_path
                        break
                except Exception:
                    continue
    
    if not book_dir:
        raise HTTPException(status_code=404, detail="Book not found")
    
    tracker = MetadataTracker(book_dir)
    metadata = tracker.load()
    
    # Find chapter entry
    chapter_found = False
    for ch in metadata.get('chapters', []):
        if ch.get('title') == chapter_title:
            if 'flagged_chunks' not in ch:
                ch['flagged_chunks'] = []
            if chunk_index not in ch['flagged_chunks']:
                ch['flagged_chunks'].append(chunk_index)
            chapter_found = True
            break
    
    if not chapter_found:
        # Add chapter entry
        if 'chapters' not in metadata:
            metadata['chapters'] = []
        metadata['chapters'].append({
            'title': chapter_title,
            'flagged_chunks': [chunk_index],
        })
    
    tracker.save()
    
    return {"status": "flagged", "chapter_title": chapter_title, "chunk_index": chunk_index}


@router.get("/api/search")
async def search_books(query: str):
    """Search Royal Road for books."""
    try:
        results = search_royal_road(query)
        return {"books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

