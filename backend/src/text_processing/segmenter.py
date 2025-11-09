"""Breath-group segmentation for TTS generation - Object-Oriented Implementation."""

import re
from typing import List, Optional

from src.text_processing.config import TextProcessingConfig
from src.text_processing.models import Segment, SegmentMetadata, generate_segment_id


class TextSegmenter:
    """Segments text into breath-groups for optimal TTS synthesis."""
    
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        """
        Initialize text segmenter.
        
        Args:
            config: Optional TextProcessingConfig instance (creates default if not provided)
        """
        self.config = config or TextProcessingConfig()
        self.seg_config = self.config.segmentation_config
    
    def segment(self, paragraph: str, position: int = 0) -> List[Segment]:
        """
        Segment a paragraph into breath-groups.
        
        Args:
            paragraph: Paragraph text to segment
            position: Position in document (for ID generation)
            
        Returns:
            List of Segment objects
        """
        max_chars = self.seg_config.get('max_chars_per_breath', 200)
        split_on_commas = self.seg_config.get('split_on_commas', True)
        split_on_dashes = self.seg_config.get('split_on_dashes', True)
        split_on_semicolons = self.seg_config.get('split_on_semicolons', True)
        
        segments = []
        
        # Check if entire paragraph is dialogue
        is_dialogue = self.detect_dialogue(paragraph)
        speaker_hint = self.extract_speaker_hint(paragraph) if is_dialogue else None
        
        # If paragraph is short enough, return as single segment
        if len(paragraph) <= max_chars:
            segment_id = generate_segment_id(paragraph, position, speaker_hint)
            segments.append(Segment(
                id=segment_id,
                text=paragraph.strip(),
                meta=SegmentMetadata(
                    is_dialogue=is_dialogue,
                    speaker_hint=speaker_hint,
                )
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
            
            part_is_dialogue = self.detect_dialogue(part)
            part_speaker = self.extract_speaker_hint(part) if part_is_dialogue else speaker_hint
            
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
                            meta=SegmentMetadata(
                                is_dialogue=is_dialogue,
                                speaker_hint=speaker_hint,
                            )
                        ))
                        segment_position += 1
                    
                    # Start new segment with dialogue
                    current_segment = [part]
                    current_length = len(part)
                    is_dialogue = part_is_dialogue
                    speaker_hint = part_speaker
            else:
                # Split non-dialogue text by natural break points
                subparts = self._split_text_by_breath_points(
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
                                meta=SegmentMetadata(
                                    is_dialogue=is_dialogue,
                                    speaker_hint=speaker_hint,
                                )
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
                meta=SegmentMetadata(
                    is_dialogue=is_dialogue,
                    speaker_hint=speaker_hint,
                )
            ))
        
        return segments
    
    def segment_all(self, paragraphs: List[str]) -> List[Segment]:
        """
        Segment all paragraphs into breath-groups.
        
        Args:
            paragraphs: List of paragraph strings
            
        Returns:
            List of Segment objects
        """
        all_segments = []
        position = 0
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            segments = self.segment(para, position)
            all_segments.extend(segments)
            position += len(segments)
        
        return all_segments
    
    @staticmethod
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
    
    @staticmethod
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
    
    def _split_text_by_breath_points(
        self,
        text: str,
        max_chars: int = 200,
        split_on_commas: bool = True,
        split_on_dashes: bool = True,
        split_on_semicolons: bool = True,
    ) -> List[str]:
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


