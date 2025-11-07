"""Text preprocessing for optimal XTTS v2 generation."""

import re
from typing import Optional
from pathlib import Path

from src.tts.normalizer import normalize
from src.tts.normalization_rules import get_default_rules, load_rules_from_file


def prepare_text_for_xtts(text: str, preserve_structure: bool = True) -> str:
    """
    Prepare text for XTTS v2 generation.
    
    XTTS v2 works best with natural, well-formatted text. This function:
    - Normalizes whitespace while preserving structure
    - Ensures proper spacing around punctuation
    - Preserves paragraph breaks and dialogue formatting
    - Removes any SSML/markup that might interfere
    
    Args:
        text: Raw text to prepare
        preserve_structure: If True, preserves paragraph breaks and formatting
        
    Returns:
        Cleaned text optimized for XTTS v2
    """
    # Remove any SSML/markup tags (if present)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize multiple spaces to single space (within lines)
    text = re.sub(r' +', ' ', text)
    
    # Normalize tabs to spaces
    text = text.replace('\t', ' ')
    
    if preserve_structure:
        # Preserve paragraph breaks (double newlines)
        # Normalize 3+ newlines to 2 (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Ensure proper spacing around sentence-ending punctuation
        # Fix cases like "word.Word" → "word. Word"
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
        
        # Fix cases like "word,word" → "word, word" (but preserve numbers)
        text = re.sub(r'([,!;:])([^\s\d])', r'\1 \2', text)
    else:
        # Single-line mode: replace all newlines with spaces
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r' +', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines but preserve paragraph breaks
    if preserve_structure:
        # Keep single empty lines (paragraph breaks)
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            if line:
                cleaned_lines.append(line)
                prev_empty = False
            elif not prev_empty:
                # First empty line = paragraph break
                cleaned_lines.append('')
                prev_empty = True
        text = '\n'.join(cleaned_lines)
    else:
        text = '\n'.join([line for line in lines if line])
    
    return text.strip()


def normalize_text(
    text: str,
    rules: Optional[dict] = None,
    rules_path: Optional[Path] = None,
) -> list[str]:
    """
    Normalize text using the full normalization pipeline.
    
    This is the new recommended preprocessing function that applies
    comprehensive normalization (punctuation, numbers, dates, acronyms).
    
    Args:
        text: Raw text to normalize
        rules: Optional normalization rules dict (if None, uses defaults or loads from file)
        rules_path: Optional path to rules config file
        
    Returns:
        List of normalized paragraphs
    """
    if rules is None:
        if rules_path and Path(rules_path).exists():
            rules = load_rules_from_file(Path(rules_path))
        else:
            rules = get_default_rules()
    
    return normalize(text, rules)


def enhance_text_pacing(text: str, add_pauses: bool = False) -> str:
    """
    Enhance text pacing for better TTS prosody.
    
    This adds natural pauses and formatting hints that XTTS v2 handles well.
    
    Args:
        text: Text to enhance
        add_pauses: If True, adds ellipses for dramatic pauses
        
    Returns:
        Enhanced text with better pacing hints
    """
    if not add_pauses:
        return text
    
    # Add pauses after dramatic moments (heuristic)
    # This is optional - XTTS v2 handles natural text well without this
    
    # Example: Add pause after exclamations in dialogue
    text = re.sub(r'!"([^"]*)"', r'!"\1"...', text)
    
    return text


def validate_text_for_xtts(text: str) -> tuple[bool, list[str]]:
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

