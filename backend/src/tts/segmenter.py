"""Breath-group segmentation for TTS generation."""

import re
import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class Segment:
    """A segment of text ready for synthesis."""
    id: str  # Deterministic UUID based on text + position
    text: str  # Ready-for-synthesis text
    meta: dict  # {is_dialogue: bool, speaker_hint: Optional[str], pacing: Optional[str]}


def generate_segment_id(text: str, position: int, voice_hint: Optional[str] = None) -> str:
    """
    Generate deterministic segment ID.
    
    Args:
        text: Segment text
        position: Position in document
        voice_hint: Optional voice hint
        
    Returns:
        Deterministic ID (SHA1 hash)
    """
    content = f"{text}|{position}|{voice_hint or ''}"
    return hashlib.sha1(content.encode('utf-8')).hexdigest()[:16]


def detect_dialogue(text: str) -> bool:
    """
    Detect if text is dialogue (quoted text).
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be dialogue
    """
    # Check for quoted text (single or double quotes)
    quoted_pattern = r'^["\'"].*["\']$'
    if re.match(quoted_pattern, text.strip()):
        return True
    
    # Check for dialogue tags (said, replied, etc.)
    dialogue_tags = ['said', 'replied', 'answered', 'asked', 'whispered', 'shouted',
                     'exclaimed', 'muttered', 'continued', 'added', 'interrupted']
    for tag in dialogue_tags:
        if re.search(rf'\b{tag}\b', text, re.IGNORECASE):
            return True
    
    return False


def extract_speaker_hint(text: str) -> Optional[str]:
    """
    Extract speaker hint from text (e.g., "Max said" → "Max").
    
    Args:
        text: Text to analyze
        
    Returns:
        Speaker name if found, None otherwise
    """
    # Pattern: "Name said/replied/etc."
    pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|replied|answered|asked|whispered|shouted|exclaimed|muttered|continued|added)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    
    # Pattern: said Name
    pattern = r'(?:said|replied|answered|asked)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def segment(
    paragraph: str,
    cfg: Optional[dict] = None,
    position: int = 0,
) -> list[Segment]:
    """
    Segment a paragraph into breath-groups.
    
    Args:
        paragraph: Paragraph text to segment
        cfg: Configuration dict with:
            - max_chars_per_breath: int (default 200)
            - split_on_commas: bool (default True)
            - split_on_dashes: bool (default True)
            - split_on_semicolons: bool (default True)
        position: Position in document (for ID generation)
        
    Returns:
        List of Segment objects
    """
    if cfg is None:
        cfg = {}
    
    max_chars = cfg.get('max_chars_per_breath', 200)
    split_on_commas = cfg.get('split_on_commas', True)
    split_on_dashes = cfg.get('split_on_dashes', True)
    split_on_semicolons = cfg.get('split_on_semicolons', True)
    
    segments = []
    
    # Check if entire paragraph is dialogue
    is_dialogue = detect_dialogue(paragraph)
    speaker_hint = extract_speaker_hint(paragraph) if is_dialogue else None
    
    # If paragraph is short enough, return as single segment
    if len(paragraph) <= max_chars:
        segment_id = generate_segment_id(paragraph, position, speaker_hint)
        segments.append(Segment(
            id=segment_id,
            text=paragraph.strip(),
            meta={
                'is_dialogue': is_dialogue,
                'speaker_hint': speaker_hint,
                'pacing': None,
            }
        ))
        return segments
    
    # Split paragraph into breath-groups
    # Priority: dialogue quotes > em-dashes > semicolons > long commas
    
    # First, handle quoted dialogue separately
    quoted_parts = re.split(r'(["\'][^"\']*["\'])', paragraph)
    
    current_segment = []
    current_length = 0
    segment_position = position
    
    for part in quoted_parts:
        if not part.strip():
            continue
        
        part_is_dialogue = detect_dialogue(part)
        part_speaker = extract_speaker_hint(part) if part_is_dialogue else speaker_hint
        
        # If part is dialogue and short, add to current segment or create new
        if part_is_dialogue and len(part) <= max_chars:
            if current_length + len(part) <= max_chars:
                current_segment.append(part)
                current_length += len(part) + 1  # +1 for space
            else:
                # Save current segment
                if current_segment:
                    segment_text = ' '.join(current_segment).strip()
                    segment_id = generate_segment_id(segment_text, segment_position, speaker_hint)
                    segments.append(Segment(
                        id=segment_id,
                        text=segment_text,
                        meta={
                            'is_dialogue': is_dialogue,
                            'speaker_hint': speaker_hint,
                            'pacing': None,
                        }
                    ))
                    segment_position += 1
                
                # Start new segment with dialogue
                current_segment = [part]
                current_length = len(part)
                is_dialogue = part_is_dialogue
                speaker_hint = part_speaker
        else:
            # Split non-dialogue text by natural break points
            subparts = split_text_by_breath_points(
                part,
                max_chars=max_chars,
                split_on_commas=split_on_commas,
                split_on_dashes=split_on_dashes,
                split_on_semicolons=split_on_semicolons,
            )
            
            for subpart in subparts:
                subpart = subpart.strip()
                if not subpart:
                    continue
                
                if current_length + len(subpart) <= max_chars:
                    current_segment.append(subpart)
                    current_length += len(subpart) + 1
                else:
                    # Save current segment
                    if current_segment:
                        segment_text = ' '.join(current_segment).strip()
                        segment_id = generate_segment_id(segment_text, segment_position, speaker_hint)
                        segments.append(Segment(
                            id=segment_id,
                            text=segment_text,
                            meta={
                                'is_dialogue': is_dialogue,
                                'speaker_hint': speaker_hint,
                                'pacing': None,
                            }
                        ))
                        segment_position += 1
                    
                    # Start new segment
                    current_segment = [subpart]
                    current_length = len(subpart)
    
    # Add final segment
    if current_segment:
        segment_text = ' '.join(current_segment).strip()
        segment_id = generate_segment_id(segment_text, segment_position, speaker_hint)
        segments.append(Segment(
            id=segment_id,
            text=segment_text,
            meta={
                'is_dialogue': is_dialogue,
                'speaker_hint': speaker_hint,
                'pacing': None,
            }
        ))
    
    return segments


def split_text_by_breath_points(
    text: str,
    max_chars: int = 200,
    split_on_commas: bool = True,
    split_on_dashes: bool = True,
    split_on_semicolons: bool = True,
) -> list[str]:
    """
    Split text at natural breath points.
    
    Args:
        text: Text to split
        max_chars: Maximum characters per segment
        split_on_commas: Split on commas
        split_on_dashes: Split on em-dashes
        split_on_semicolons: Split on semicolons
        
    Returns:
        List of text segments
    """
    if len(text) <= max_chars:
        return [text]
    
    parts = []
    current_pos = 0
    
    while current_pos < len(text):
        # Find next break point
        remaining = text[current_pos:]
        
        if len(remaining) <= max_chars:
            parts.append(remaining)
            break
        
        # Look for break points in the last portion of max_chars
        search_start = max(0, max_chars - 100)  # Look in last 100 chars
        search_text = remaining[search_start:max_chars + 50]
        
        break_pos = None
        
        # Priority: em-dash > semicolon > comma
        if split_on_dashes:
            dash_match = re.search(r'—', search_text)
            if dash_match:
                break_pos = search_start + dash_match.end()
        
        if break_pos is None and split_on_semicolons:
            semicolon_match = re.search(r';\s+', search_text)
            if semicolon_match:
                break_pos = search_start + semicolon_match.end()
        
        if break_pos is None and split_on_commas:
            # Find last comma before max_chars
            comma_matches = list(re.finditer(r',\s+', search_text))
            if comma_matches:
                # Use last comma that's not too close to start
                for match in reversed(comma_matches):
                    pos = search_start + match.end()
                    if pos > 50:  # Don't break too early
                        break_pos = pos
                        break
        
        if break_pos is None:
            # No good break point found, split at max_chars
            break_pos = max_chars
        
        parts.append(remaining[:break_pos].strip())
        current_pos += break_pos
    
    return [p for p in parts if p.strip()]


def segment_all(
    paragraphs: list[str],
    cfg: Optional[dict] = None,
) -> list[Segment]:
    """
    Segment all paragraphs into breath-groups.
    
    Args:
        paragraphs: List of paragraph strings
        cfg: Configuration dict (see segment function)
        
    Returns:
        List of Segment objects
    """
    all_segments = []
    position = 0
    
    for para in paragraphs:
        if not para.strip():
            continue
        
        segments = segment(para, cfg, position)
        all_segments.extend(segments)
        position += len(segments)
    
    return all_segments

