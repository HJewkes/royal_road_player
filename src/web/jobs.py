"""Background job management for scraping and TTS generation."""

import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"  # Replaced by a newer job


class JobType(str, Enum):
    """Job type enumeration."""
    SCRAPE_BOOK = "scrape_book"
    GENERATE_AUDIO = "generate_audio"
    GENERATE_CHAPTER_AUDIO = "generate_chapter_audio"
    GENERATE_CHUNK_AUDIO = "generate_chunk_audio"


class JobManager:
    """Manage background jobs for scraping and TTS generation."""
    
    def __init__(self):
        """Initialize job manager."""
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.settings = get_settings()
        
        # Separate queues for scraping and audio generation
        self.scraping_queue: list[str] = []  # Job IDs waiting to run
        self.audio_queue: list[str] = []  # Job IDs waiting to run
        self.running_scraping_job: Optional[str] = None  # Currently running scraping job
        self.running_audio_job: Optional[str] = None  # Currently running audio job
        
        # Load persisted jobs from disk
        self._load_jobs()
        
        # Start queue processors
        self._start_queue_processors()
    
    def _get_jobs_file(self) -> Path:
        """Get path to jobs persistence file."""
        return self.settings.data_dir / "jobs.json"
    
    def _load_jobs(self) -> None:
        """Load jobs from disk."""
        jobs_file = self._get_jobs_file()
        if jobs_file.exists():
            try:
                with open(jobs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Only load non-running jobs (running jobs need to be restarted)
                    self.jobs = {
                        job_id: job_data
                        for job_id, job_data in data.items()
                        if job_data.get('status') != JobStatus.RUNNING
                    }
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")
    
    def _save_jobs(self) -> None:
        """Save jobs to disk."""
        jobs_file = self._get_jobs_file()
        jobs_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(jobs_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")
    
    def create_job(
        self,
        job_type: JobType,
        book_id: Optional[str] = None,
        chapter_title: Optional[str] = None,
        book_url: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Create a new job.
        
        Args:
            job_type: Type of job
            book_id: Book ID (for audio generation)
            chapter_title: Chapter title (for chapter audio generation)
            book_url: Book URL (for scraping)
            **kwargs: Additional job parameters
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job_data = {
            'id': job_id,
            'type': job_type.value,
            'status': JobStatus.PENDING.value,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'progress': 0,
            'message': 'Job queued',
            'book_id': book_id,
            'chapter_title': chapter_title,
            'book_url': book_url,
            'parameters': kwargs,
        }
        
        self.jobs[job_id] = job_data
        
        # Mark old failed jobs for the same chapter as superseded
        if chapter_title and job_type in (JobType.GENERATE_CHAPTER_AUDIO, JobType.GENERATE_CHUNK_AUDIO):
            for old_job_id, old_job in list(self.jobs.items()):
                if (old_job_id != job_id and
                    old_job.get('chapter_title') == chapter_title and
                    old_job.get('book_id') == book_id and
                    old_job.get('status') == JobStatus.FAILED.value and
                    old_job.get('type') in ('generate_chapter_audio', 'generate_chunk_audio')):
                    old_job['status'] = JobStatus.SUPERSEDED.value
                    old_job['updated_at'] = datetime.utcnow().isoformat()
                    old_job['message'] = 'Superseded by new generation job'
                    logger.info(f"Marked old failed job {old_job_id} as superseded")
        
        self._save_jobs()
        
        # Add to appropriate queue instead of starting immediately
        job_type = JobType(job_data['type'])
        if job_type == JobType.SCRAPE_BOOK:
            self.scraping_queue.append(job_id)
            logger.info(f"Added scraping job {job_id} to queue (position {len(self.scraping_queue)})")
        elif job_type in (JobType.GENERATE_AUDIO, JobType.GENERATE_CHAPTER_AUDIO, JobType.GENERATE_CHUNK_AUDIO):
            self.audio_queue.append(job_id)
            logger.info(f"Added audio job {job_id} to queue (position {len(self.audio_queue)})")
        
        # Trigger queue processing
        self._process_queues()
        
        return job_id
    
    def _run_job_sync(self, job_id: str) -> None:
        """Synchronous wrapper for running jobs in background thread."""
        import asyncio
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_job(job_id))
        except Exception as e:
            logger.error(f"Error in job thread for {job_id}: {e}")
            job = self.jobs.get(job_id)
            if job:
                job['status'] = JobStatus.FAILED.value
                job['message'] = f"Error: {str(e)}"
                job['updated_at'] = datetime.utcnow().isoformat()
                self._save_jobs()
        finally:
            # Clear running job flags
            if self.running_scraping_job == job_id:
                self.running_scraping_job = None
            if self.running_audio_job == job_id:
                self.running_audio_job = None
    
    async def _run_job(self, job_id: str) -> None:
        """Run a job in the background."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        job['status'] = JobStatus.RUNNING.value
        job['updated_at'] = datetime.utcnow().isoformat()
        job['message'] = 'Starting job...'
        self._save_jobs()
        
        try:
            job_type = JobType(job['type'])
            
            if job_type == JobType.SCRAPE_BOOK:
                await self._run_scrape_job(job_id)
            elif job_type == JobType.GENERATE_AUDIO:
                await self._run_generate_audio_job(job_id)
            elif job_type == JobType.GENERATE_CHAPTER_AUDIO:
                await self._run_generate_chapter_audio_job(job_id)
            elif job_type == JobType.GENERATE_CHUNK_AUDIO:
                await self._run_generate_chunk_audio_job(job_id)
            else:
                raise ValueError(f"Unknown job type: {job_type}")
                
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job['status'] = JobStatus.FAILED.value
            job['message'] = f"Error: {str(e)}"
            job['updated_at'] = datetime.utcnow().isoformat()
            self._save_jobs()
    
    async def _run_scrape_job(self, job_id: str) -> None:
        """Run a book scraping job."""
        job = self.jobs[job_id]
        book_url = job['book_url']
        filter_book_number = job['parameters'].get('filter_book_number')
        
        # Run scraper in subprocess
        # Use the scripts/scrape_book.py script
        # Find Python executable (prefer venv if available)
        import sys
        python_exe = sys.executable
        
        cmd = [
            python_exe, str(Path(__file__).parent.parent.parent / 'scripts' / 'scrape_book.py'),
            book_url,
        ]
        if filter_book_number:
            cmd.extend(['--book-number', str(filter_book_number)])
        
        # Run from project root
        project_root = Path(__file__).parent.parent.parent
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
        )
        
        self.processes[job_id] = process
        
        job['message'] = 'Scraping chapters...'
        self._save_jobs()
        
        # Monitor process
        try:
            stdout, stderr = await asyncio.to_thread(process.communicate)
            
            if process.returncode == 0:
                job['status'] = JobStatus.COMPLETED.value
                job['message'] = 'Scraping completed successfully'
                job['progress'] = 100
            else:
                job['status'] = JobStatus.FAILED.value
                job['message'] = f"Scraping failed: {stderr[:200]}"
        except Exception as e:
            job['status'] = JobStatus.FAILED.value
            job['message'] = f"Error: {str(e)}"
        finally:
            self.processes.pop(job_id, None)
            job['updated_at'] = datetime.utcnow().isoformat()
            self._save_jobs()
    
    async def _run_generate_audio_job(self, job_id: str) -> None:
        """Run audio generation for a book."""
        job = self.jobs[job_id]
        book_id = job['book_id']
        
        # Find book directory
        book_dir = None
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            book_dir = dir_path
                            break
                    except Exception:
                        continue
        
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        chapters_dir = book_dir / "chapters"
        text_files = sorted(chapters_dir.glob("*.txt"))
        
        job['message'] = f'Generating audio for {len(text_files)} chapters...'
        job['parameters']['total_chapters'] = len(text_files)
        self._save_jobs()
        
        # Generate audio for each chapter
        for idx, text_file in enumerate(text_files):
            if job['status'] == JobStatus.CANCELLED.value:
                break
            
            # Check if chapter already has audio (skip if complete)
            chapter_title = text_file.stem
            chunk_files = list((text_file.parent).glob(f"{chapter_title}_chunk_*.wav"))
            if len(chunk_files) > 0:
                # Chapter already has chunks, skip
                logger.info(f"Skipping {text_file.name} - already has {len(chunk_files)} chunks")
                continue
            
            job['message'] = f'Generating audio for chapter {idx + 1}/{len(text_files)}'
            job['progress'] = int((idx / len(text_files)) * 100)
            self._save_jobs()
            
            # Run audio generation
            import sys
            python_exe = sys.executable
            project_root = Path(__file__).parent.parent.parent
            
            cmd = [
                python_exe, str(project_root / 'scripts' / 'generate_audio.py'),
                str(text_file),
                '--chunked',
                '--chunk-duration', '1.0',
            ]
            
            if job['parameters'].get('speaker'):
                cmd.extend(['--speaker', job['parameters']['speaker']])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(project_root),
            )
            
            self.processes[job_id] = process
            
            try:
                stdout, stderr = await asyncio.to_thread(process.communicate)
                if process.returncode != 0:
                    logger.warning(f"Failed to generate audio for {text_file.name}: {stderr[:200]}")
            except Exception as e:
                logger.error(f"Error generating audio for {text_file.name}: {e}")
            finally:
                self.processes.pop(job_id, None)
        
        job['status'] = JobStatus.COMPLETED.value
        job['message'] = 'Audio generation completed'
        job['progress'] = 100
        job['updated_at'] = datetime.utcnow().isoformat()
        self._save_jobs()
    
    async def _run_generate_chapter_audio_job(self, job_id: str) -> None:
        """Run audio generation for a single chapter."""
        job = self.jobs[job_id]
        book_id = job['book_id']
        chapter_title = job['chapter_title']
        
        # Find book directory
        book_dir = None
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            book_dir = dir_path
                            break
                    except Exception:
                        continue
        
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        text_file = book_dir / "chapters" / f"{chapter_title}.txt"
        if not text_file.exists():
            raise ValueError(f"Chapter not found: {chapter_title}")
        
        job['message'] = 'Generating audio...'
        self._save_jobs()
        
        import sys
        python_exe = sys.executable
        project_root = Path(__file__).parent.parent.parent
        
        cmd = [
            python_exe, str(project_root / 'scripts' / 'generate_audio.py'),
            str(text_file),
            '--chunked',
            '--chunk-duration', '1.0',
        ]
        
        if job['parameters'].get('speaker'):
            cmd.extend(['--speaker', job['parameters']['speaker']])
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout for easier streaming
            text=True,
            cwd=str(project_root),
            bufsize=1,  # Line buffered
        )
        
        self.processes[job_id] = process
        
        stdout_lines = []
        
        def read_output():
            """Read process output line by line (runs in thread)."""
            lines = []
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break
                if output:
                    lines.append(output.strip())
            return lines, process.poll()
        
        try:
            # Stream output line by line for live updates (in background thread)
            stdout_lines, return_code = await asyncio.to_thread(read_output)
            
            # Process lines and update job status
            for line in stdout_lines:
                # Update job message with latest progress
                if 'Generating chunk' in line or 'chunk' in line.lower():
                    job['message'] = line
                    self._save_jobs()
                elif 'Loading TTS model' in line:
                    job['message'] = 'Loading TTS model...'
                    self._save_jobs()
                elif 'Created' in line and 'chunks' in line:
                    job['message'] = line
                    self._save_jobs()
                logger.debug(f"Job {job_id} output: {line}")
            
            stdout = '\n'.join(stdout_lines)
            
            if return_code == 0:
                job['status'] = JobStatus.COMPLETED.value
                job['message'] = 'Audio generation completed'
                job['progress'] = 100
            else:
                job['status'] = JobStatus.FAILED.value
                # Include full output for debugging
                error_msg = f"Generation failed (exit code {return_code})"
                if stdout:
                    # Get last 2000 chars of output
                    error_output = stdout[-2000:] if len(stdout) > 2000 else stdout
                    error_msg += f"\n\nOutput:\n{error_output}"
                job['message'] = error_msg
                logger.error(f"Job {job_id} failed: {error_msg}")
        except Exception as e:
            job['status'] = JobStatus.FAILED.value
            job['message'] = f"Error: {str(e)}"
            logger.error(f"Job {job_id} exception: {e}", exc_info=True)
        finally:
            self.processes.pop(job_id, None)
            job['updated_at'] = datetime.utcnow().isoformat()
            self._save_jobs()
    
    async def _run_generate_chunk_audio_job(self, job_id: str) -> None:
        """Run audio generation for a specific chunk."""
        job = self.jobs[job_id]
        book_id = job['book_id']
        chapter_title = job['chapter_title']
        chunk_index = job['parameters'].get('chunk_index')
        
        if not chunk_index:
            raise ValueError("chunk_index is required for chunk generation")
        
        # Find book directory
        book_dir = None
        for dir_path in self.settings.books_dir.iterdir():
            if dir_path.is_dir() and book_id in dir_path.name:
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('book_id') == book_id:
                            book_dir = dir_path
                            break
                    except Exception:
                        continue
        
        if not book_dir:
            raise ValueError(f"Book not found: {book_id}")
        
        text_file = book_dir / "chapters" / f"{chapter_title}.txt"
        if not text_file.exists():
            raise ValueError(f"Chapter not found: {chapter_title}")
        
        job['message'] = f'Generating chunk {chunk_index}...'
        self._save_jobs()
        
        # Check if chunk is flagged - if so, delete it first
        chunk_file = text_file.parent / f"{chapter_title}_chunk_{chunk_index:03d}.wav"
        
        # Capture existing chunks BEFORE generation
        existing_chunks_before = set(text_file.parent.glob(f"{chapter_title}_chunk_*.wav"))
        
        if chunk_file.exists():
            # Check if flagged
            from src.utils.metadata_tracker import MetadataTracker
            tracker = MetadataTracker(book_dir)
            metadata = tracker.load()
            chapter_meta = next((ch for ch in metadata.get('chapters', []) if ch.get('title') == chapter_title), {})
            flagged_chunks = chapter_meta.get('flagged_chunks', [])
            
            if chunk_index in flagged_chunks:
                # Delete the chunk file to force regeneration
                chunk_file.unlink()
                logger.info(f"Deleted flagged chunk file: {chunk_file.name}")
                existing_chunks_before.discard(chunk_file)  # Remove from set since we deleted it
        
        # Generate audio - the generator will only generate missing chunks
        import sys
        python_exe = sys.executable
        project_root = Path(__file__).parent.parent.parent
        
        cmd = [
            python_exe, str(project_root / 'scripts' / 'generate_audio.py'),
            str(text_file),
            '--chunked',
            '--chunk-duration', '1.0',
        ]
        
        if job['parameters'].get('speaker'):
            cmd.extend(['--speaker', job['parameters']['speaker']])
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout for easier streaming
            text=True,
            cwd=str(project_root),
            bufsize=1,  # Line buffered
        )
        
        self.processes[job_id] = process
        
        stdout_lines = []
        
        def read_output():
            """Read process output line by line (runs in thread)."""
            lines = []
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break
                if output:
                    lines.append(output.strip())
            return lines, process.poll()
        
        try:
            # Stream output line by line for live updates (in background thread)
            stdout_lines, return_code = await asyncio.to_thread(read_output)
            
            # Process lines and update job status
            for line in stdout_lines:
                # Update job message with latest progress
                if f'chunk_{chunk_index:03d}' in line or f'Chunk {chunk_index}' in line:
                    job['message'] = f'Generating chunk {chunk_index}: {line}'
                    self._save_jobs()
                elif 'Generating chunk' in line:
                    job['message'] = line
                    self._save_jobs()
                logger.debug(f"Job {job_id} output: {line}")
            
            stdout = '\n'.join(stdout_lines)
            
            if return_code == 0:
                # Check if the chunk was actually generated
                # Note: The generator will generate ALL missing chunks, not just the specific one
                # So we check if ANY new chunks were generated
                existing_chunks_after = set(text_file.parent.glob(f"{chapter_title}_chunk_*.wav"))
                new_chunks = existing_chunks_after - existing_chunks_before
                
                if chunk_file.exists() or new_chunks:
                    # Refresh metadata to reflect new chunks
                    from src.utils.metadata_tracker import MetadataTracker
                    tracker = MetadataTracker(book_dir)
                    tracker.refresh_from_filesystem()
                    
                    # Also try to update chunk metadata if we can read the text file
                    try:
                        # Re-run chunking to get positions and update metadata
                        from src.tts.chunker import chunk_text_by_paragraphs
                        text_content = text_file.read_text(encoding='utf-8')
                        chunk_data = chunk_text_by_paragraphs(
                            text_content,
                            target_chars_per_minute=int(1.0 * 800),  # ~1 minute chunks
                            max_chars=250,  # XTTS v2 limit
                            return_positions=True,
                        )
                        
                        # Load existing metadata to preserve generation times
                        existing_metadata = tracker.load()
                        existing_chapter_meta = next(
                            (ch for ch in existing_metadata.get('chapters', []) if ch.get('title') == chapter_title),
                            {}
                        )
                        existing_chunk_meta_dict = {
                            m.get('index'): m for m in existing_chapter_meta.get('chunk_metadata', [])
                        }
                        
                        # Build chunk metadata for ALL chunks (completed and pending)
                        chunk_metadata = []
                        for i, chunk_info in enumerate(chunk_data, 1):
                            if isinstance(chunk_info, tuple):
                                chunk_text, start_pos, end_pos = chunk_info
                            else:
                                chunk_text = chunk_info
                                start_pos = text_content.find(chunk_text)
                                end_pos = start_pos + len(chunk_text) if start_pos >= 0 else len(chunk_text)
                            
                            chunk_file_check = text_file.parent / f"{chapter_title}_chunk_{i:03d}.wav"
                            chunk_exists = chunk_file_check.exists()
                            
                            # Preserve existing metadata if available
                            existing_meta = existing_chunk_meta_dict.get(i, {})
                            
                            chunk_metadata.append({
                                'index': i,
                                'text_start': start_pos,
                                'text_end': end_pos,
                                'text_length': len(chunk_text),
                                'status': 'completed' if chunk_exists else 'pending',
                                'generation_time_seconds': existing_meta.get('generation_time_seconds') if chunk_exists else None,
                                'created_at': existing_meta.get('created_at') if chunk_exists else None,
                            })
                        
                        # Update metadata with all chunks (completed and pending)
                        tracker.update_chunk_metadata(chapter_title, chunk_metadata)
                        # Update count to reflect only completed chunks
                        completed_count = sum(1 for cm in chunk_metadata if cm.get('status') == 'completed')
                        tracker.update_chunk_count(chapter_title, completed_count)
                        tracker.mark_chapter_audio_generated(chapter_title)
                    except Exception as e:
                        logger.warning(f"Failed to update detailed chunk metadata: {e}")
                        # At least update the count
                        completed_count = len(existing_chunks_after)
                        tracker.update_chunk_count(chapter_title, completed_count)
                    
                    job['status'] = JobStatus.COMPLETED.value
                    if chunk_file.exists():
                        job['message'] = f'Chunk {chunk_index} generated successfully'
                    else:
                        job['message'] = f'Generated {len(new_chunks)} new chunk(s) (chunk {chunk_index} may have been skipped if it already exists)'
                    job['progress'] = 100
                else:
                    job['status'] = JobStatus.FAILED.value
                    job['message'] = f'Chunk {chunk_index} was not generated (may already exist or generation skipped it)'
            else:
                job['status'] = JobStatus.FAILED.value
                # Include full output for debugging
                error_msg = f"Generation failed (exit code {return_code})"
                if stdout:
                    # Get last 2000 chars of output
                    error_output = stdout[-2000:] if len(stdout) > 2000 else stdout
                    error_msg += f"\n\nOutput:\n{error_output}"
                job['message'] = error_msg
                logger.error(f"Job {job_id} failed: {error_msg}")
        except Exception as e:
            job['status'] = JobStatus.FAILED.value
            job['message'] = f"Error: {str(e)}"
            logger.error(f"Job {job_id} exception: {e}", exc_info=True)
        finally:
            self.processes.pop(job_id, None)
            job['updated_at'] = datetime.utcnow().isoformat()
            self._save_jobs()
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if job was cancelled, False otherwise
        """
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job['status'] == JobStatus.RUNNING.value:
            # Kill process if running
            process = self.processes.get(job_id)
            if process:
                process.terminate()
                self.processes.pop(job_id, None)
        
        job['status'] = JobStatus.CANCELLED.value
        job['updated_at'] = datetime.utcnow().isoformat()
        job['message'] = 'Job cancelled'
        self._save_jobs()
        
        return True
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, book_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        List all jobs, optionally filtered by book_id.
        
        Args:
            book_id: Optional book ID to filter by
            
        Returns:
            List of job dictionaries (excluding superseded jobs)
        """
        jobs = list(self.jobs.values())
        if book_id:
            jobs = [j for j in jobs if j.get('book_id') == book_id]
        # Filter out superseded jobs
        jobs = [j for j in jobs if j.get('status') != JobStatus.SUPERSEDED.value]
        return sorted(jobs, key=lambda x: x['created_at'], reverse=True)
    
    def _start_queue_processors(self) -> None:
        """Start background threads to process queues."""
        import threading
        
        def process_scraping_queue():
            """Process scraping queue (one at a time)."""
            while True:
                try:
                    if not self.running_scraping_job and self.scraping_queue:
                        job_id = self.scraping_queue.pop(0)
                        self.running_scraping_job = job_id
                        logger.info(f"Starting scraping job {job_id}")
                        self._run_job_sync(job_id)
                        self.running_scraping_job = None
                    import time
                    time.sleep(1)  # Check every second
                except Exception as e:
                    logger.error(f"Error in scraping queue processor: {e}")
                    import time
                    time.sleep(5)
        
        def process_audio_queue():
            """Process audio queue (one at a time to avoid GPU conflicts)."""
            while True:
                try:
                    if not self.running_audio_job and self.audio_queue:
                        job_id = self.audio_queue.pop(0)
                        self.running_audio_job = job_id
                        logger.info(f"Starting audio job {job_id}")
                        self._run_job_sync(job_id)
                        self.running_audio_job = None
                    import time
                    time.sleep(1)  # Check every second
                except Exception as e:
                    logger.error(f"Error in audio queue processor: {e}")
                    import time
                    time.sleep(5)
        
        # Start queue processor threads
        scraping_thread = threading.Thread(target=process_scraping_queue, daemon=True)
        scraping_thread.start()
        
        audio_thread = threading.Thread(target=process_audio_queue, daemon=True)
        audio_thread.start()
    
    def _process_queues(self) -> None:
        """Trigger queue processing (called after adding jobs)."""
        # Queues are processed by background threads, this is just a trigger
        pass


# Global job manager instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get global job manager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager

