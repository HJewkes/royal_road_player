"""Track book metadata including scraping, TTS, and chunk progress."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MetadataTracker:
    """Track and update book metadata."""
    
    def __init__(self, book_dir: Path):
        """
        Initialize metadata tracker for a book.
        
        Args:
            book_dir: Path to book directory
        """
        self.book_dir = Path(book_dir)
        self.metadata_path = self.book_dir / "metadata.json"
        self._metadata: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        Load metadata from file.
        
        Returns:
            Metadata dictionary
        """
        if self._metadata is not None:
            return self._metadata
        
        if not self.metadata_path.exists():
            self._metadata = {
                'book_id': '',
                'book_title': '',
                'book_url': '',
                'chapters': [],
                'scraping': {
                    'total_chapters': 0,
                    'scraped_chapters': 0,
                    'last_scraped': None,
                },
                'tts': {
                    'total_chapters': 0,
                    'generated_chapters': 0,
                    'last_generated': None,
                },
                'chunks': {
                    'total_chunks': 0,
                    'chunks_by_chapter': {},
                },
            }
            return self._metadata
        
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self._metadata = json.load(f)
            
            # Ensure required sections exist
            if 'scraping' not in self._metadata:
                self._metadata['scraping'] = {
                    'total_chapters': 0,
                    'scraped_chapters': 0,
                    'last_scraped': None,
                }
            if 'tts' not in self._metadata:
                self._metadata['tts'] = {
                    'total_chapters': 0,
                    'generated_chapters': 0,
                    'last_generated': None,
                }
            if 'chunks' not in self._metadata:
                self._metadata['chunks'] = {
                    'total_chunks': 0,
                    'chunks_by_chapter': {},
                }
            
            return self._metadata
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load metadata from {self.metadata_path}: {e}")
            self._metadata = {
                'book_id': '',
                'book_title': '',
                'book_url': '',
                'chapters': [],
                'scraping': {
                    'total_chapters': 0,
                    'scraped_chapters': 0,
                    'last_scraped': None,
                },
                'tts': {
                    'total_chapters': 0,
                    'generated_chapters': 0,
                    'last_generated': None,
                },
                'chunks': {
                    'total_chunks': 0,
                    'chunks_by_chapter': {},
                },
            }
            return self._metadata
    
    def save(self) -> None:
        """Save metadata to file."""
        if self._metadata is None:
            return
        
        try:
            self.book_dir.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save metadata to {self.metadata_path}: {e}")
    
    def mark_chapter_scraped(self, chapter_title: str, word_count: Optional[int] = None) -> None:
        """
        Mark a chapter as scraped.
        
        Args:
            chapter_title: Chapter title/filename
            word_count: Optional word count
        """
        metadata = self.load()
        
        # Update chapter entry if it exists
        chapter_found = False
        for ch in metadata.get('chapters', []):
            if ch.get('title') == chapter_title:
                ch['scraped'] = True
                ch['scraped_at'] = datetime.utcnow().isoformat()
                if word_count is not None:
                    ch['word_count'] = word_count
                chapter_found = True
                break
        
        # If chapter not in list, add it
        if not chapter_found:
            if 'chapters' not in metadata:
                metadata['chapters'] = []
            metadata['chapters'].append({
                'title': chapter_title,
                'scraped': True,
                'scraped_at': datetime.utcnow().isoformat(),
                'word_count': word_count,
            })
        
        # Update scraping stats
        scraping = metadata['scraping']
        scraping['last_scraped'] = datetime.utcnow().isoformat()
        
        # Recalculate scraped count
        scraping['scraped_chapters'] = sum(
            1 for ch in metadata.get('chapters', [])
            if ch.get('scraped', False)
        )
        scraping['total_chapters'] = len(metadata.get('chapters', []))
        
        self.save()
    
    def mark_chapter_audio_generated(self, chapter_title: str, audio_path: Optional[str] = None) -> None:
        """
        Mark a chapter as having audio generated.
        
        Args:
            chapter_title: Chapter title/filename
            audio_path: Optional path to audio file
        """
        metadata = self.load()
        
        # Update chapter entry
        chapter_found = False
        for ch in metadata.get('chapters', []):
            if ch.get('title') == chapter_title:
                ch['has_audio'] = True
                ch['audio_generated_at'] = datetime.utcnow().isoformat()
                if audio_path:
                    ch['audio_path'] = audio_path
                chapter_found = True
                break
        
        # If chapter not in list, add it
        if not chapter_found:
            if 'chapters' not in metadata:
                metadata['chapters'] = []
            metadata['chapters'].append({
                'title': chapter_title,
                'has_audio': True,
                'audio_generated_at': datetime.utcnow().isoformat(),
                'audio_path': audio_path,
            })
        
        # Update TTS stats
        tts = metadata['tts']
        tts['last_generated'] = datetime.utcnow().isoformat()
        
        # Recalculate generated count
        tts['generated_chapters'] = sum(
            1 for ch in metadata.get('chapters', [])
            if ch.get('has_audio', False)
        )
        tts['total_chapters'] = len(metadata.get('chapters', []))
        
        self.save()
    
    def update_chunk_count(self, chapter_title: str, chunk_count: int) -> None:
        """
        Update chunk count for a chapter.
        
        Args:
            chapter_title: Chapter title/filename
            chunk_count: Number of chunks
        """
        metadata = self.load()
        
        # Update chapter entry
        chapter_found = False
        for ch in metadata.get('chapters', []):
            if ch.get('title') == chapter_title:
                ch['chunk_count'] = chunk_count
                ch['is_chunked'] = chunk_count > 0
                chapter_found = True
                break
        
        # If chapter not in list, add it
        if not chapter_found:
            if 'chapters' not in metadata:
                metadata['chapters'] = []
            metadata['chapters'].append({
                'title': chapter_title,
                'chunk_count': chunk_count,
                'is_chunked': chunk_count > 0,
            })
        
        # Update chunks stats
        chunks = metadata['chunks']
        chunks['chunks_by_chapter'][chapter_title] = chunk_count
        
        # Recalculate total chunks
        chunks['total_chunks'] = sum(chunks['chunks_by_chapter'].values())
        
        self.save()
    
    def update_chunk_metadata(self, chapter_title: str, chunk_metadata: list[dict]) -> None:
        """
        Update detailed chunk metadata for a chapter.
        
        Args:
            chapter_title: Chapter title/filename
            chunk_metadata: List of chunk metadata dicts with keys:
                - index: Chunk index (1-based)
                - text_start: Start position in text
                - text_end: End position in text
                - text_length: Length of chunk text
                - generation_time_seconds: Time taken to generate (optional)
                - status: 'pending', 'running', 'completed', 'failed'
                - created_at: Timestamp (optional)
        """
        metadata = self.load()
        
        # Find or create chapter entry
        chapter_found = False
        for ch in metadata.get('chapters', []):
            if ch.get('title') == chapter_title:
                ch['chunk_metadata'] = chunk_metadata
                chapter_found = True
                break
        
        if not chapter_found:
            if 'chapters' not in metadata:
                metadata['chapters'] = []
            metadata['chapters'].append({
                'title': chapter_title,
                'chunk_metadata': chunk_metadata,
            })
        
        self.save()
    
    def refresh_from_filesystem(self) -> None:
        """Refresh metadata by scanning filesystem."""
        metadata = self.load()
        chapters_dir = self.book_dir / "chapters"
        
        if not chapters_dir.exists():
            return
        
        # Scan for text files (scraped chapters)
        text_files = sorted(chapters_dir.glob("*.txt"))
        scraped_titles = {f.stem for f in text_files}
        
        # Scan for audio files
        audio_files = list(chapters_dir.glob("*.wav"))
        audio_titles = set()
        for audio_file in audio_files:
            # Remove _chunk_XXX suffix if present
            title = audio_file.stem
            if '_chunk_' in title:
                title = title.rsplit('_chunk_', 1)[0]
            audio_titles.add(title)
        
        # Scan for chunks
        chunk_files = list(chapters_dir.glob("*_chunk_*.wav"))
        chunks_by_chapter: Dict[str, int] = {}
        for chunk_file in chunk_files:
            # Extract chapter title from chunk filename
            title = chunk_file.stem.rsplit('_chunk_', 1)[0]
            chunks_by_chapter[title] = chunks_by_chapter.get(title, 0) + 1
        
        # Update metadata
        scraping = metadata['scraping']
        scraping['scraped_chapters'] = len(scraped_titles)
        scraping['total_chapters'] = len(scraped_titles)
        
        tts = metadata['tts']
        tts['generated_chapters'] = len(audio_titles)
        tts['total_chapters'] = len(scraped_titles)
        
        chunks = metadata['chunks']
        chunks['chunks_by_chapter'] = chunks_by_chapter
        chunks['total_chunks'] = sum(chunks_by_chapter.values())
        
        # Update chapter entries
        all_titles = scraped_titles | audio_titles | set(chunks_by_chapter.keys())
        for title in all_titles:
            chapter_found = False
            for ch in metadata.get('chapters', []):
                if ch.get('title') == title:
                    ch['scraped'] = title in scraped_titles
                    ch['has_audio'] = title in audio_titles
                    ch['chunk_count'] = chunks_by_chapter.get(title, 0)
                    ch['is_chunked'] = chunks_by_chapter.get(title, 0) > 0
                    chapter_found = True
                    break
            
            if not chapter_found:
                if 'chapters' not in metadata:
                    metadata['chapters'] = []
                metadata['chapters'].append({
                    'title': title,
                    'scraped': title in scraped_titles,
                    'has_audio': title in audio_titles,
                    'chunk_count': chunks_by_chapter.get(title, 0),
                    'is_chunked': chunks_by_chapter.get(title, 0) > 0,
                })
        
        self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics.
        
        Returns:
            Dictionary with scraping, TTS, and chunk statistics
        """
        metadata = self.load()
        return {
            'scraping': metadata.get('scraping', {}),
            'tts': metadata.get('tts', {}),
            'chunks': metadata.get('chunks', {}),
        }

