"""FastAPI routes for the audiobook API."""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from src.api.requests import (
    AddFictionRequest,
    ImportPatreonBooksRequest,
    BackfillResult,
    BackfillTitlesRequest,
    ChunkRequest,
    DownloadRequest,
    EmitEventRequest,
    ExportRequest,
    FictionInfo,
    FictionPreview,
    GenerateRequest,
    NormalizeRequest,
    SeriesBookInfo,
    ValidateRequest,
)
from src.cache import get_royal_road_cache, get_book_status_cache
from src.config import get_settings
from src.discovery import (
    BookDiscovery,
    ChapterDiscovery,
    ChunkDiscovery,
    get_book_discovery,
    get_chapter_discovery,
    get_chunk_discovery,
)
from src.events import get_event_store
from src.export import get_exporter
from src.models import BookStatus, BookSummary, ChapterSummary, OperationResult, QueueStatus
from src.queue import Job, get_job_queue, get_download_queue
from src.scraper import get_scraper
from src.text import TextChunker, TextNormalizer, TableConverter, StatBlockConverter
from src.text.renderings import UnrenderedSpecBlockError, render_or_raise
from src.tts import get_tts_engine
from src.tts.verified import synthesize_verified
from src.validation.phonemes import get_phoneme_recognizer
from src.utils import (
    extract_series_name,
    FictionIdPath,
    BookNumberPath,
    ChapterNumberPath,
    BookNumberQuery,
)
from src.validation import get_audio_validator

logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan and App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting audiobook-v2 server...")
    settings = get_settings()

    # Start background processors if enabled
    if settings.enable_background_processor:
        asyncio.create_task(start_processor())
        asyncio.create_task(start_download_processor())

    yield

    # Cleanup
    logger.info("Shutting down...")
    job_queue = get_job_queue()
    await job_queue.stop_processing()
    download_queue = get_download_queue()
    await download_queue.stop_processing()


app = FastAPI(
    title="Audiobook V2 API",
    description="Streamlined audiobook production system",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Background Processor
# ============================================================================

async def start_processor():
    """Start the background job processor."""
    settings = get_settings()
    queue = get_job_queue()
    tts = get_tts_engine()
    exporter = get_exporter()

    # Load the phoneme recognizer once so self-healing synthesis doesn't reload it
    # per chunk. If verification is off (or the model is unavailable) this is skipped.
    recognizer = None
    if settings.verify_synthesis:
        try:
            recognizer = get_phoneme_recognizer()
        except Exception as exc:
            logger.warning(f"Self-healing synthesis disabled — recognizer load failed: {exc}")

    def process_job(job: Job) -> tuple[Path, float]:
        """Process a single chunk job, self-healing hallucinated takes."""
        chunks_dir = get_chunk_discovery().get_chunks_dir(
            job.fiction_id, job.book_number, job.chapter_number
        )
        output_path = chunks_dir / f"{job.chunk_index:03d}.wav"

        if recognizer is not None:
            return synthesize_verified(
                tts, job.text, output_path,
                recognizer=recognizer, retries=settings.verify_max_retries,
            )
        return tts.synthesize(job.text, output_path)

    async def on_chapter_complete(fiction_id: str, book_number: int, chapter_number: int):
        """Export chapter when all chunks complete."""
        logger.info(f"Auto-exporting chapter {chapter_number}")
        path = exporter.export_chapter(fiction_id, book_number, chapter_number)
        if path:
            get_event_store().emit(
                "chapter.completed",
                fiction_id=fiction_id,
                book=book_number,
                chapter=chapter_number,
                detail={"export_path": str(path)},
            )

    await queue.start_processing(
        process_fn=process_job,
        on_chapter_complete=on_chapter_complete,
    )


async def start_download_processor():
    """Start the download job processor."""
    download_queue = get_download_queue()

    def do_download(fiction_id: str, book_number: int, on_progress):
        """Download a book with progress tracking."""
        source = _detect_source(fiction_id)
        scraper = get_scraper(source)
        if source == "patreon":
            # For Patreon books stored under a Royal Road fiction_id,
            # we need the Patreon URL to know where to fetch from
            patreon_url = _get_patreon_url(fiction_id)
            if patreon_url:
                patreon_fid, _ = _parse_source_url(patreon_url)
                scraper.download_book(
                    fiction_id, book_number,
                    on_progress=on_progress,
                    fetch_fiction_id=patreon_fid,
                )
                return
        scraper.download_book(fiction_id, book_number, on_progress=on_progress)

    await download_queue.start_processing(do_download)


# ============================================================================
# Discovery Routes
# ============================================================================


def _extract_series_name(title: str) -> str:
    """Extract series name from book title by removing '- Book N' suffix."""
    return extract_series_name(title)


@app.get("/api/fictions")
async def list_fictions() -> list[FictionInfo]:
    """List all fictions with their names."""
    discovery = get_book_discovery()
    fictions = []
    for fiction_id in discovery.list_fictions():
        books = discovery.list_books(fiction_id)
        if books:
            # Get series name from first book's title
            name = _extract_series_name(books[0].title)
        else:
            name = f"Fiction {fiction_id}"
        fictions.append(FictionInfo(fiction_id=fiction_id, name=name))
    return fictions


def _detect_source(fiction_id: str) -> str:
    """Detect whether a fiction uses Patreon or Royal Road."""
    if fiction_id.startswith("patreon_"):
        return "patreon"
    settings = get_settings()
    meta_path = Path(settings.books_dir) / fiction_id / "patreon_meta.json"
    if meta_path.exists():
        return "patreon"
    return "royal_road"


def _get_patreon_url(fiction_id: str) -> str | None:
    """Get the Patreon URL for a fiction from its metadata."""
    settings = get_settings()
    meta_path = Path(settings.books_dir) / fiction_id / "patreon_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f).get("patreon_url")
    return None


def _get_patreon_series_index(fiction_id: str) -> int | None:
    """Read the series_index from a Patreon fiction's metadata file."""
    settings = get_settings()
    meta_path = Path(settings.books_dir) / fiction_id / "patreon_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        return meta.get("series_index")
    # Try to extract from fiction_id pattern like patreon_tedsteel_s1
    m = re.search(r'_s(\d+)$', fiction_id)
    return int(m.group(1)) if m else None


def _get_patreon_base_fiction_id(fiction_id: str) -> str:
    """Strip the _sN suffix to get the base fiction_id for API calls."""
    return re.sub(r'_s\d+$', '', fiction_id)


def _parse_source_url(url: str) -> tuple[str, str]:
    """Parse a URL into (fiction_id, source).

    Returns:
        Tuple of (fiction_id, source) where source is "royal_road" or "patreon"
    """
    rr_match = re.search(r'royalroad\.com/fiction/(\d+)', url)
    if rr_match:
        return rr_match.group(1), "royal_road"

    pt_match = re.search(r'patreon\.com/c/([^/]+)', url)
    if pt_match:
        slug = pt_match.group(1)
        return f"patreon_{slug}", "patreon"

    return None, None


@app.post("/api/fictions/preview")
async def preview_fiction(request: AddFictionRequest) -> FictionPreview:
    """Preview a fiction from URL without adding it."""
    fiction_id, source = _parse_source_url(request.url)
    if not fiction_id:
        raise HTTPException(status_code=400, detail="Invalid URL. Supported: Royal Road, Patreon")

    scraper = get_scraper(source)

    try:
        info = scraper.get_fiction_info(fiction_id)

        if source == "patreon":
            books = scraper.get_books_from_posts(fiction_id)
        else:
            books = scraper.get_all_books_in_series(fiction_id)

        return FictionPreview(
            fiction_id=fiction_id,
            title=info["title"],
            author=info.get("author"),
            url=info["url"],
            book_count=len(books),
            books=books,
            source=source,
        )
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch fiction {fiction_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch fiction: {str(e)}")


@app.post("/api/fictions/add")
async def add_fiction(request: AddFictionRequest) -> FictionInfo:
    """Add a fiction to the library by URL."""
    fiction_id, source = _parse_source_url(request.url)
    if not fiction_id:
        raise HTTPException(status_code=400, detail="Invalid URL. Supported: Royal Road, Patreon")

    scraper = get_scraper(source)
    discovery = get_book_discovery()

    existing = discovery.list_fictions()
    if fiction_id in existing:
        books = discovery.list_books(fiction_id)
        if books:
            name = _extract_series_name(books[0].title)
        else:
            info = scraper.get_fiction_info(fiction_id)
            name = info["title"]
        return FictionInfo(fiction_id=fiction_id, name=name)

    try:
        info = scraper.get_fiction_info(fiction_id)
        settings = get_settings()
        fiction_path = Path(settings.books_dir) / fiction_id
        fiction_path.mkdir(parents=True, exist_ok=True)

        return FictionInfo(fiction_id=fiction_id, name=info["title"])
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add fiction {fiction_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to add fiction: {str(e)}")


@app.post("/api/fictions/import-patreon")
async def import_patreon_books(request: ImportPatreonBooksRequest):
    """Import selected books from Patreon into a fiction (existing or new)."""
    fiction_id = request.fiction_id
    discovery = get_book_discovery()
    settings = get_settings()
    download_queue = get_download_queue()

    # Ensure fiction directory exists
    fiction_path = Path(settings.books_dir) / fiction_id
    if not fiction_path.exists():
        fiction_path.mkdir(parents=True, exist_ok=True)

    # Save patreon metadata so download processor knows to use PatreonScraper
    meta_path = fiction_path / "patreon_meta.json"
    meta = {
        "source": "patreon",
        "patreon_url": request.patreon_url,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # Queue downloads for each selected book
    scraper = get_scraper("patreon")
    patreon_fiction_id, _ = _parse_source_url(request.patreon_url)
    queued = []
    for book_number in request.book_numbers:
        try:
            chapters = scraper.get_chapter_list(patreon_fiction_id, book_number)
            total_chapters = len(chapters)
        except Exception:
            total_chapters = 0

        job = await download_queue.add_job(
            fiction_id, book_number, total_chapters=total_chapters
        )
        queued.append({"book_number": book_number, "job_id": job.job_id})

    return OperationResult(
        success=True,
        message=f"Queued {len(queued)} book(s) for download from Patreon",
        data={"queued": queued},
    )


@app.get("/api/series/{fiction_id}")
async def get_series_info(fiction_id: FictionIdPath, refresh: bool = False) -> list[SeriesBookInfo]:
    """Get all books in a series, merged with local download status."""
    is_patreon = fiction_id.startswith("patreon_")
    source = "patreon" if is_patreon else "royal_road"

    cache = get_royal_road_cache()
    cache_key = f"series:{fiction_id}"

    if not refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return _merge_with_local_status(fiction_id, cached)

    scraper = get_scraper(source)
    try:
        if is_patreon:
            series_index = _get_patreon_series_index(fiction_id)
            source_books = scraper.get_books_from_posts(fiction_id, series_index=series_index)
        else:
            source_books = scraper.get_all_books_in_series(fiction_id)
        cache.set(cache_key, source_books)
        logger.info(f"Cached source data for fiction {fiction_id}: {len(source_books)} books")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch from source: {e}")
        return _get_local_only_books(fiction_id)

    return _merge_with_local_status(fiction_id, source_books)


def _merge_with_local_status(fiction_id: str, rr_books: list[dict]) -> list[SeriesBookInfo]:
    """Merge Royal Road book data with local download status."""
    discovery = get_book_discovery()
    local_books = {b.book_number: b for b in discovery.list_books(fiction_id)}
    
    result = []
    seen_books = set()
    
    for rr_book in rr_books:
        book_num = rr_book["book_number"]
        seen_books.add(book_num)
        
        if book_num in local_books:
            local = local_books[book_num]
            result.append(SeriesBookInfo(
                book_number=book_num,
                chapter_count=local.chapter_count,
                is_downloaded=True,
                chapters_normalized=local.chapters_normalized,
                chapters_chunked=local.chapters_chunked,
                chapters_complete=local.chapters_complete,
                progress_percent=local.progress_percent,
                status=local.status,
                chapters_on_source=rr_book.get("chapter_count"),
            ))
        else:
            result.append(SeriesBookInfo(
                book_number=book_num,
                chapter_count=rr_book["chapter_count"],
                is_downloaded=False,
                status=BookStatus.AVAILABLE,
            ))
    
    # Add local-only books
    for book_num, local in local_books.items():
        if book_num not in seen_books:
            result.append(SeriesBookInfo(
                book_number=book_num,
                chapter_count=local.chapter_count,
                is_downloaded=True,
                chapters_normalized=local.chapters_normalized,
                chapters_chunked=local.chapters_chunked,
                chapters_complete=local.chapters_complete,
                progress_percent=local.progress_percent,
                status=local.status,
            ))
    
    result.sort(key=lambda x: x.book_number)
    return result


def _get_local_only_books(fiction_id: str) -> list[SeriesBookInfo]:
    """Get only locally downloaded books (fallback when Royal Road is unavailable)."""
    discovery = get_book_discovery()
    local_books = discovery.list_books(fiction_id)
    
    return sorted([
        SeriesBookInfo(
            book_number=b.book_number,
            chapter_count=b.chapter_count,
            is_downloaded=True,
            chapters_normalized=b.chapters_normalized,
            chapters_chunked=b.chapters_chunked,
            chapters_complete=b.chapters_complete,
            progress_percent=b.progress_percent,
            status=b.status,
        )
        for b in local_books
    ], key=lambda x: x.book_number)


@app.get("/api/series-local/{fiction_id}")
async def get_series_local(fiction_id: FictionIdPath) -> list[SeriesBookInfo]:
    """
    Fast endpoint: Get only locally downloaded books without hitting Royal Road.
    
    Use this for frequent polling/updates. Use /api/series/{fiction_id} for
    full series info including undownloaded books.
    """
    return _get_local_only_books(fiction_id)


@app.get("/api/books/{fiction_id}")
async def list_books(fiction_id: FictionIdPath) -> list[BookSummary]:
    """List all books for a fiction, sorted by book number."""
    books = get_book_discovery().list_books(fiction_id)
    # Sort by book_number numerically
    return sorted(books, key=lambda b: b.book_number)


@app.get("/api/books/{fiction_id}/{book_number}")
async def get_book(fiction_id: FictionIdPath, book_number: BookNumberPath):
    """Get book details."""
    book = get_book_discovery().get_book(fiction_id, book_number)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.get("/api/books/{fiction_id}/{book_number}/chapters")
async def list_chapters(fiction_id: FictionIdPath, book_number: BookNumberPath) -> list[ChapterSummary]:
    """List all chapters for a book."""
    return get_chapter_discovery().list_chapters(fiction_id, book_number)


@app.get("/api/books/{fiction_id}/{book_number}/chapters/{chapter_number}")
async def get_chapter(fiction_id: FictionIdPath, book_number: BookNumberPath, chapter_number: ChapterNumberPath):
    """Get chapter details."""
    chapter = get_chapter_discovery().get_chapter(fiction_id, book_number, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


# ============================================================================
# Scraping Routes
# ============================================================================

@app.get("/api/scraper/preview")
async def preview_chapters(fiction_id: FictionIdPath, book_number: BookNumberQuery = None):
    """Preview available chapters without downloading."""
    is_patreon = fiction_id.startswith("patreon_")
    source = "patreon" if is_patreon else "royal_road"
    scraper = get_scraper(source)
    return scraper.get_chapter_list(fiction_id, book_number)


@app.post("/api/scraper/download")
async def download_book(request: DownloadRequest):
    """Download a book (runs in background with progress tracking)."""
    download_queue = get_download_queue()
    is_patreon = request.fiction_id.startswith("patreon_")
    source = "patreon" if is_patreon else "royal_road"

    scraper = get_scraper(source)
    try:
        chapters = scraper.get_chapter_list(request.fiction_id, request.book_number)
        total_chapters = len(chapters)
    except Exception:
        total_chapters = 0

    job = await download_queue.add_job(
        request.fiction_id,
        request.book_number,
        total_chapters=total_chapters,
    )

    return OperationResult(
        success=True,
        message="Download queued",
        data={"job_id": job.job_id, "total_chapters": total_chapters},
    )


@app.get("/api/downloads/status")
async def get_download_status():
    """Get status of all download jobs."""
    download_queue = get_download_queue()
    return download_queue.get_status()


@app.get("/api/downloads/{fiction_id}/{book_number}")
async def get_download_job_status(fiction_id: FictionIdPath, book_number: BookNumberPath):
    """Get status of a specific download job."""
    download_queue = get_download_queue()
    job = download_queue.get_job(fiction_id, book_number)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "message": job.message,
        "progress_chapters": job.progress_chapters,
        "total_chapters": job.total_chapters,
        "progress_percent": job.progress_percent,
    }


# ============================================================================
# Backfill Routes
# ============================================================================


@app.post("/api/backfill/titles")
async def backfill_chapter_titles(request: BackfillTitlesRequest) -> BackfillResult:
    """
    Backfill chapter titles and source URLs from Royal Road.

    This only updates metadata.json files and does NOT affect:
    - raw.txt, normalized.txt
    - chunks/
    - audio files
    - validation results
    - export status
    """
    if request.fiction_id.startswith("patreon_"):
        return BackfillResult(
            success=False,
            message="Backfill not supported for Patreon fictions",
            updated=0, skipped=0, errors=[],
        )

    scraper = get_scraper()
    chapter_discovery = get_chapter_discovery()
    settings = get_settings()

    # Get chapters from Royal Road
    try:
        rr_chapters = scraper.get_chapter_list(request.fiction_id, request.book_number)
    except Exception as e:
        logger.error(f"Failed to fetch chapters from Royal Road: {e}")
        return BackfillResult(
            success=False,
            message=f"Failed to fetch from Royal Road: {str(e)}",
            updated=0,
            skipped=0,
            errors=[str(e)],
        )

    if not rr_chapters:
        return BackfillResult(
            success=False,
            message="No chapters found on Royal Road for this book",
            updated=0,
            skipped=0,
            errors=["No chapters found"],
        )

    # Get local chapters
    local_chapters = chapter_discovery.list_chapters(request.fiction_id, request.book_number)

    # Build a mapping of RR chapter index (1-based) to RR chapter info
    rr_by_index = {i + 1: ch for i, ch in enumerate(rr_chapters)}

    updated = 0
    skipped = 0
    errors = []

    for local_ch in local_chapters:
        ch_num = local_ch.chapter_number
        chapter_dir = chapter_discovery.get_chapter_path(
            request.fiction_id, request.book_number, ch_num
        )
        metadata_path = chapter_dir / "metadata.json"

        if not metadata_path.exists():
            errors.append(f"Chapter {ch_num}: metadata.json not found")
            continue

        # Find matching RR chapter (by index position)
        rr_ch = rr_by_index.get(ch_num)
        if not rr_ch:
            skipped += 1
            continue

        # Check if title already has real content (not just "Chapter N")
        rr_title = rr_ch.get("title", "")
        is_generic_rr = bool(re.match(r'^Chapter\s+\d+$', rr_title, re.I))

        if is_generic_rr:
            # Royal Road also has generic title, skip
            skipped += 1
            continue

        try:
            # Load existing metadata
            with open(metadata_path) as f:
                metadata = json.load(f)

            # Check if local title is generic
            local_title = metadata.get("title", "")
            is_generic_local = bool(re.match(r'^Chapter\s+\d+$', local_title, re.I))

            if not is_generic_local:
                # Local title already has content, skip unless source_url is missing
                if metadata.get("source_url"):
                    skipped += 1
                    continue

            # Update title and source_url
            metadata["title"] = rr_title
            metadata["source_url"] = rr_ch.get("url")

            # Write back
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2, default=str)

            updated += 1
            logger.info(f"Updated chapter {ch_num}: {rr_title}")

        except Exception as e:
            errors.append(f"Chapter {ch_num}: {str(e)}")
            logger.error(f"Failed to update chapter {ch_num}: {e}")

    return BackfillResult(
        success=True,
        message=f"Backfill complete: {updated} updated, {skipped} skipped",
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


@app.get("/api/backfill/preview/{fiction_id}/{book_number}")
async def preview_backfill(fiction_id: FictionIdPath, book_number: BookNumberPath):
    """
    Preview what would be updated by a title backfill operation.

    Returns list of chapters with current and new titles.
    """
    if fiction_id.startswith("patreon_"):
        raise HTTPException(status_code=400, detail="Backfill not supported for Patreon")

    scraper = get_scraper()
    chapter_discovery = get_chapter_discovery()

    # Get chapters from Royal Road
    try:
        rr_chapters = scraper.get_chapter_list(fiction_id, book_number)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch from Royal Road: {str(e)}")

    # Get local chapters
    local_chapters = chapter_discovery.list_chapters(fiction_id, book_number)

    # Build mapping
    rr_by_index = {i + 1: ch for i, ch in enumerate(rr_chapters)}

    preview = []
    for local_ch in local_chapters:
        ch_num = local_ch.chapter_number
        rr_ch = rr_by_index.get(ch_num)

        current_title = local_ch.title
        new_title = rr_ch.get("title", "") if rr_ch else None

        # Determine if update would happen
        is_generic_local = bool(re.match(r'^Chapter\s+\d+$', current_title, re.I))
        is_generic_rr = bool(re.match(r'^Chapter\s+\d+$', new_title or "", re.I)) if new_title else True

        would_update = is_generic_local and not is_generic_rr

        preview.append({
            "chapter_number": ch_num,
            "current_title": current_title,
            "new_title": new_title,
            "would_update": would_update,
        })

    return {
        "fiction_id": fiction_id,
        "book_number": book_number,
        "chapters": preview,
        "total_would_update": sum(1 for p in preview if p["would_update"]),
    }


# ============================================================================
# Text Processing Routes
# ============================================================================

@app.post("/api/normalize")
async def normalize_chapters(request: NormalizeRequest):
    """Normalize chapter text for TTS."""
    chapter_discovery = get_chapter_discovery()
    normalizer = TextNormalizer()
    table_converter = TableConverter()
    stat_block_converter = StatBlockConverter()

    chapters = chapter_discovery.list_chapters(request.fiction_id, request.book_number)
    if request.chapter_numbers:
        chapters = [c for c in chapters if c.chapter_number in request.chapter_numbers]

    normalized = 0
    for chapter_sum in chapters:
        raw_text = chapter_discovery.get_raw_text(
            request.fiction_id, request.book_number, chapter_sum.chapter_number
        )
        if not raw_text:
            continue

        # Rephrase stats tables first: pipe tables (TableConverter) and whitespace
        # roster/record blocks (StatBlockConverter) — disjoint, order-independent.
        text = table_converter.convert(raw_text)
        text = stat_block_converter.convert(text)
        # Then substitute pinned renderings for tables no converter claimed. This
        # raises rather than passing an unrendered table through: spoken verbatim
        # it becomes a minute of "Acceleration ex-ex", and the audio would sound
        # fine to STT validation because it faithfully renders unspeakable text.
        try:
            text = render_or_raise(
                text,
                chapter_discovery.get_chapter_path(
                    request.fiction_id, request.book_number, chapter_sum.chapter_number
                ),
            )
        except UnrenderedSpecBlockError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        # Then normalize
        text = normalizer.normalize(text)

        chapter_discovery.save_normalized_text(
            request.fiction_id, request.book_number, chapter_sum.chapter_number, text
        )
        normalized += 1

    return OperationResult(
        success=True,
        message=f"Normalized {normalized} chapters",
        data={"count": normalized},
    )


@app.post("/api/chunk")
async def chunk_chapters(request: ChunkRequest):
    """Chunk normalized text for TTS."""
    chapter_discovery = get_chapter_discovery()
    chunk_discovery = get_chunk_discovery()
    chunker = TextChunker()

    chapters = chapter_discovery.list_chapters(request.fiction_id, request.book_number)
    if request.chapter_numbers:
        chapters = [c for c in chapters if c.chapter_number in request.chapter_numbers]

    total_chunks = 0
    for chapter_sum in chapters:
        normalized_text = chapter_discovery.get_normalized_text(
            request.fiction_id, request.book_number, chapter_sum.chapter_number
        )
        if not normalized_text:
            continue

        # Chunk the text
        chunk_results = chunker.chunk(normalized_text)

        # Save chunks
        chunks_data = [(c.index, c.text) for c in chunk_results]
        chunk_discovery.save_chunks(
            request.fiction_id, request.book_number, chapter_sum.chapter_number, chunks_data
        )
        total_chunks += len(chunk_results)

    return OperationResult(
        success=True,
        message=f"Created {total_chunks} chunks",
        data={"count": total_chunks},
    )


# ============================================================================
# Audio Generation Routes
# ============================================================================

@app.post("/api/generate")
async def queue_generation(request: GenerateRequest):
    """Queue chapters for audio generation."""
    chunk_discovery = get_chunk_discovery()
    queue = get_job_queue()

    chapters = get_chapter_discovery().list_chapters(request.fiction_id, request.book_number)
    if request.chapter_numbers:
        chapters = [c for c in chapters if c.chapter_number in request.chapter_numbers]

    jobs_added = 0
    for chapter_sum in chapters:
        pending = chunk_discovery.get_pending_chunks(
            request.fiction_id, request.book_number, chapter_sum.chapter_number
        )

        chunks_data = [(c.index, c.text) for c in pending]
        added = queue.add_chapter(
            request.fiction_id,
            request.book_number,
            chapter_sum.chapter_number,
            chunks_data,
        )
        jobs_added += added

    return OperationResult(
        success=True,
        message=f"Queued {jobs_added} chunks for generation",
        data={"count": jobs_added},
    )


@app.get("/api/queue/status")
async def get_queue_status() -> QueueStatus:
    """Get current queue status."""
    return get_job_queue().get_status()


@app.get("/api/queue/chapter/{fiction_id}/{book_number}/{chapter_number}")
async def get_chapter_queue_status(
    fiction_id: FictionIdPath,
    book_number: BookNumberPath,
    chapter_number: ChapterNumberPath
):
    """Get queue status for a specific chapter."""
    return get_job_queue().get_chapter_status(fiction_id, book_number, chapter_number)


@app.post("/api/queue/retry")
async def retry_failed(job_id: Optional[str] = None):
    """Retry failed jobs."""
    count = get_job_queue().retry_failed(job_id)
    return OperationResult(success=True, message=f"Retrying {count} jobs")


# ============================================================================
# Validation Routes
# ============================================================================

@app.post("/api/validate")
async def validate_chapter(request: ValidateRequest):
    """Validate a chapter's audio against source text."""
    validator = get_audio_validator()
    result = validator.validate_chapter(
        request.fiction_id, request.book_number, request.chapter_number
    )

    if not result:
        raise HTTPException(status_code=400, detail="Validation failed")

    return result


@app.get("/api/validation/{fiction_id}/{book_number}/{chapter_number}")
async def get_validation_results(
    fiction_id: FictionIdPath,
    book_number: BookNumberPath,
    chapter_number: ChapterNumberPath
):
    """Get saved validation results for a chapter."""
    validator = get_audio_validator()
    result = validator.get_validation_result(fiction_id, book_number, chapter_number)

    if not result:
        raise HTTPException(status_code=404, detail="Validation results not found")

    return result


# ============================================================================
# Export Routes
# ============================================================================

@app.post("/api/export")
async def export_chapter(request: ExportRequest):
    """Export a chapter to audio file."""
    exporter = get_exporter()
    path = exporter.export_chapter(
        request.fiction_id,
        request.book_number,
        request.chapter_number,
        request.format,
    )

    if not path:
        raise HTTPException(status_code=400, detail="Export failed")

    get_event_store().emit(
        "chapter.completed",
        fiction_id=request.fiction_id,
        book=request.book_number,
        chapter=request.chapter_number,
        detail={"export_path": str(path), "format": request.format},
    )

    return OperationResult(
        success=True,
        message=f"Exported to {path}",
        data={"path": str(path)},
    )


@app.get("/api/export/status/{fiction_id}/{book_number}")
async def get_export_status(fiction_id: FictionIdPath, book_number: BookNumberPath):
    """Get export status for all chapters in a book."""
    return get_exporter().get_export_status(fiction_id, book_number)


# ============================================================================
# Event Routes
# ============================================================================


@app.get("/api/events")
async def get_events(since: int = 0, type: Optional[str] = None, limit: int = 200):
    """Return pipeline events with id > since (the poll surface for agents)."""
    events = get_event_store().read(since=since, type=type, limit=limit)
    cursor = events[-1]["id"] if events else since
    return {"events": events, "cursor": cursor}


@app.post("/api/events")
async def post_event(request: EmitEventRequest):
    """Emit a pipeline event. Used by external producers such as autopull.sh."""
    return get_event_store().emit(
        request.type,
        fiction_id=request.fiction_id,
        book=request.book,
        chapter=request.chapter,
        severity=request.severity,
        detail=request.detail,
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}

