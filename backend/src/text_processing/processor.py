"""Unified text processor that combines all transformations in a single pass."""

import re
from typing import Optional, List
from bs4 import BeautifulSoup
from markdownify import markdownify as md

import attr

from src.text_processing.config import TextProcessingConfig
from src.text_processing.normalizer import TextNormalizer
from src.text_processing.segmenter import TextSegmenter
from src.text_processing.models import Segment


@attr.s(auto_attribs=True)
class ProcessingConfig:
    """Configuration for text processing."""
    # HTML extraction
    extract_html: bool = True
    preserve_paragraphs: bool = True
    
    # Text cleaning (done once, in order)
    remove_html_tags: bool = True
    remove_markdown_links: bool = True
    remove_html_artifacts: bool = True  # Zero-width spaces, non-breaking spaces
    
    # Whitespace normalization (done once)
    normalize_tabs: bool = True
    normalize_spaces: bool = True  # Multiple spaces → single space
    normalize_newlines: bool = True  # 3+ newlines → 2
    strip_lines: bool = True
    remove_empty_lines: bool = False  # Keep empty lines for paragraph breaks
    
    # Punctuation fixes
    fix_punctuation_spacing: bool = True  # "word.Word" → "word. Word"
    
    # Content normalization
    normalize_punctuation: bool = True  # Quotes, dashes, ellipsis
    normalize_acronyms: bool = True
    normalize_numbers: bool = True
    normalize_dates: bool = True
    
    # Segmentation
    segment_into_breath_groups: bool = False
    max_chars_per_breath: int = 200
    
    # Chunking
    chunk_for_tts: bool = False
    target_chars_per_minute: int = 9000
    min_chars: int = 3000
    max_chars: int = 250


class UnifiedTextProcessor:
    """
    Unified text processor that combines all transformations in a single pass.
    
    This eliminates redundant processing - whitespace is normalized once,
    paragraphs are handled once, etc.
    """
    
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        """
        Initialize unified text processor.
        
        Args:
            config: Optional TextProcessingConfig instance
        """
        self.config = config or TextProcessingConfig()
        self.normalizer = TextNormalizer(self.config)
        self.segmenter = TextSegmenter(self.config)
    
    def process_html(
        self,
        html_content: str,
        processing_config: Optional[ProcessingConfig] = None,
    ) -> str | List[str] | List[Segment]:
        """
        Process HTML content through unified pipeline in a single pass.
        
        Args:
            html_content: Raw HTML content
            processing_config: Processing configuration (uses defaults if not provided)
            
        Returns:
            Processed text, chunks, or segments depending on config
        """
        if processing_config is None:
            processing_config = ProcessingConfig()
        
        # Step 1: Extract HTML to text (if needed)
        if processing_config.extract_html:
            text = self._extract_html_unified(html_content, processing_config)
        else:
            text = html_content
        
        # Step 2: Apply all transformations in one pass
        text = self._process_text_unified(text, processing_config)
        
        # Step 3: Segment if requested
        if processing_config.segment_into_breath_groups:
            return self._segment_unified(text, processing_config)
        
        # Step 4: Chunk if requested
        if processing_config.chunk_for_tts:
            return self._chunk_unified(text, processing_config)
        
        return text
    
    def process_text(
        self,
        text: str,
        processing_config: Optional[ProcessingConfig] = None,
    ) -> str | List[str] | List[Segment]:
        """
        Process text content through unified pipeline in a single pass.
        
        Args:
            text: Raw text content
            processing_config: Processing configuration (uses defaults if not provided)
            
        Returns:
            Processed text, chunks, or segments depending on config
        """
        if processing_config is None:
            processing_config = ProcessingConfig(extract_html=False)
        
        # Apply all transformations in one pass
        text = self._process_text_unified(text, processing_config)
        
        # Segment if requested
        if processing_config.segment_into_breath_groups:
            return self._segment_unified(text, processing_config)
        
        # Chunk if requested
        if processing_config.chunk_for_tts:
            return self._chunk_unified(text, processing_config)
        
        return text
    
    def _extract_html_unified(self, html_content: str, config: ProcessingConfig) -> str:
        """Extract text from HTML with unified processing."""
        soup = BeautifulSoup(html_content, "lxml")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Convert to markdown
        markdown_text = md(
            str(soup),
            heading_style="ATX",
            bullets="-",
            convert=["p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i", "ul", "ol", "li", "table", "tr", "td", "th", "blockquote", "code", "pre", "a"],
        )
        
        # Remove markdown links if requested
        if config.remove_markdown_links:
            markdown_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown_text)
        
        # Now process the extracted text through unified pipeline
        return self._process_text_unified(markdown_text, config)
    
    def _process_text_unified(self, text: str, config: ProcessingConfig) -> str:
        """
        Apply all text transformations in a single pass.
        
        This combines what was previously done in:
        - formatter.clean_text()
        - preprocessor.prepare_text_for_xtts()
        - normalizer.normalize_whitespace()
        - normalizer.normalize_punctuation()
        etc.
        """
        # 0. Normalize scene break markers first (before other processing)
        # This converts markers like ***, ---, \*\*\* to paragraph breaks
        text = self.normalizer.normalize_scene_breaks(text)
        
        # 1. Remove HTML tags if present
        if config.remove_html_tags:
            text = re.sub(r'<[^>]+>', '', text)
        
        # 2. Remove HTML artifacts (zero-width spaces, non-breaking spaces)
        if config.remove_html_artifacts:
            text = text.replace("\xa0", " ")  # Non-breaking space
            text = text.replace("\u200b", "")  # Zero-width space
            text = text.replace("\u200c", "")  # Zero-width non-joiner
            text = text.replace("\u200d", "")  # Zero-width joiner
        
        # 3. Normalize tabs to spaces (once)
        if config.normalize_tabs:
            text = text.replace('\t', ' ')
        
        # 4. Normalize multiple spaces to single space (once)
        if config.normalize_spaces:
            text = re.sub(r' +', ' ', text)
        
        # 5. Fix punctuation spacing (before we split into lines)
        if config.fix_punctuation_spacing:
            # Fix cases like "word.Word" → "word. Word"
            text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
            # Fix cases like "word,word" → "word, word" (but preserve numbers)
            text = re.sub(r'([,!;:])([^\s\d])', r'\1 \2', text)
        
        # 6. Split into lines and process line-by-line
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            # Strip line if requested
            if config.strip_lines:
                # Preserve markdown structure (tables, headings, lists)
                if line.strip().startswith(('|', '#', '-')) and len(line.strip()) > 1:
                    line = line.rstrip()  # Only strip trailing
                else:
                    line = line.strip()
            
            # Handle empty lines
            if not line:
                if config.remove_empty_lines:
                    continue  # Skip empty lines
                elif config.preserve_paragraphs:
                    # Keep single empty line for paragraph breaks
                    if not processed_lines or processed_lines[-1]:
                        processed_lines.append('')
                    continue
            
            processed_lines.append(line)
        
        text = '\n'.join(processed_lines)
        
        # 7. Normalize newlines (3+ → 2) if preserving paragraphs
        if config.normalize_newlines and config.preserve_paragraphs:
            text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 8. Content normalization (punctuation, numbers, dates, acronyms)
        if config.normalize_punctuation:
            text = self.normalizer.normalize_punctuation(text)
        
        if config.normalize_acronyms:
            text = self.normalizer.normalize_acronyms(text)
        
        if config.normalize_numbers:
            text = self.normalizer.normalize_numbers(text)
        
        if config.normalize_dates:
            text = self.normalizer.normalize_dates(text)
        
        # Final trim
        return text.strip()
    
    def _segment_unified(self, text: str, config: ProcessingConfig) -> List[Segment]:
        """Segment text into breath-groups."""
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # Update segmenter config if needed
        if config.max_chars_per_breath != 200:
            seg_config = self.config.segmentation_config.copy()
            seg_config['max_chars_per_breath'] = config.max_chars_per_breath
            temp_config = TextProcessingConfig()
            temp_config._config.update(self.config._config)
            temp_config._config.update(seg_config)
            segmenter = TextSegmenter(temp_config)
        else:
            segmenter = self.segmenter
        
        return segmenter.segment_all(paragraphs)
    
    def _chunk_unified(self, text: str, config: ProcessingConfig) -> List[str]:
        """Chunk text for TTS generation."""
        from src.text_processing.chunker import TextChunker
        
        chunker = TextChunker()
        chunks = chunker.chunk_by_paragraphs(
            text,
            target_chars_per_minute=config.target_chars_per_minute,
            min_chars=config.min_chars,
            max_chars=config.max_chars,
        )
        
        # Extract text from chunks (for backward compatibility with List[str] return)
        # Note: This loses position information, but maintains API compatibility
        return [text[chunk.text_start:chunk.text_end] for chunk in chunks]


# Convenience functions for common use cases
def process_html_for_storage(html_content: str) -> str:
    """
    Process HTML for storage (minimal processing, preserves structure).
    
    This is what should be saved to text.txt files.
    """
    config = ProcessingConfig(
        extract_html=True,
        normalize_punctuation=False,  # Don't normalize for storage
        normalize_acronyms=False,
        normalize_numbers=False,
        normalize_dates=False,
        segment_into_breath_groups=False,
        chunk_for_tts=False,
    )
    processor = UnifiedTextProcessor()
    return processor.process_html(html_content, config)


def process_text_for_tts(text: str) -> List[str]:
    """
    Process text for TTS generation (full normalization + chunking).
    
    This is what should be used when generating audio.
    """
    config = ProcessingConfig(
        extract_html=False,
        normalize_punctuation=True,
        normalize_acronyms=True,
        normalize_numbers=True,
        normalize_dates=True,
        segment_into_breath_groups=False,
        chunk_for_tts=True,
        max_chars=250,  # XTTS v2 limit
    )
    processor = UnifiedTextProcessor()
    result = processor.process_text(text, config)
    return result if isinstance(result, list) else [result]


def validate_text_for_tts(text: str) -> tuple[bool, list[str]]:
    """
    Validate text for XTTS v2 compatibility.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Check for SSML/markup
    if re.search(r'<[^>]+>', text):
        warnings.append("Found HTML/XML tags - will be stripped")
    
    # Check for excessive punctuation
    if text.count('...') > len(text) / 100:
        warnings.append("Many ellipses detected - may affect pacing")
    
    # Check for very long lines (no paragraph breaks)
    lines = text.split('\n')
    long_lines = [i for i, line in enumerate(lines, 1) if len(line) > 500]
    if long_lines:
        warnings.append(f"Long lines detected (lines {long_lines[:5]}) - consider adding paragraph breaks")
    
    # Check for proper punctuation
    sentences = re.split(r'[.!?]', text)
    sentences_without_punctuation = [s for s in sentences if s.strip() and not s.strip()[-1].isalnum()]
    if len(sentences_without_punctuation) > len(sentences) * 0.1:
        warnings.append("Some sentences may be missing punctuation")
    
    return len(warnings) == 0, warnings

