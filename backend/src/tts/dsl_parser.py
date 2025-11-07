"""Micro-SSML DSL parser for TTS annotations."""

import re
from dataclasses import dataclass
from typing import Union, List, Optional


@dataclass
class Event:
    """Non-speech timeline event."""
    kind: str  # "pause" | "scene_break" | "epigraph_start" | "epigraph_end"
    ms: int  # Duration in milliseconds (for pauses)


# Import Segment from segmenter (avoid circular import)
from src.tts.segmenter import Segment


def parse_dsl(text: str) -> List[Union[Segment, Event]]:
    """
    Parse micro-SSML DSL tags from text.
    
    Supported tags:
    - [voice=Name] → switch active voice
    - [pause:MS] → timeline pause (milliseconds)
    - [slow]...[/slow], [fast]...[/fast] → pacing hints
    - [epigraph]...[/epigraph] → style marker
    - [scene-break] or *** → scene separator
    
    Args:
        text: Text containing DSL tags
        
    Returns:
        Interleaved list of Segment and Event objects
    """
    output = []
    current_pos = 0
    active_voice = None
    active_pacing = None
    in_epigraph = False
    
    # Pattern to match DSL tags (case-insensitive)
    tag_pattern = re.compile(
        r'\[(voice=[^\]]+|pause:\d+|slow|fast|/slow|/fast|epigraph|/epigraph|scene-break)\](.*?)(?=\[|$)',
        re.IGNORECASE | re.DOTALL
    )
    
    # Also match standalone scene breaks (***)
    scene_break_pattern = re.compile(r'\*\*\*')
    
    # Find all tags and their positions
    matches = []
    for match in tag_pattern.finditer(text):
        matches.append((match.start(), match.end(), match))
    
    # Process text between tags
    last_end = 0
    
    for i, (start, end, match) in enumerate(matches):
        # Add text before this tag
        if start > last_end:
            text_before = text[last_end:start].strip()
            if text_before:
                # Create segment for text before tag
                segment = create_segment_from_text(
                    text_before,
                    position=len(output),
                    voice_hint=active_voice,
                    pacing=active_pacing,
                    is_epigraph=in_epigraph,
                )
                output.append(segment)
        
        # Process tag
        tag_content = match.group(1).lower()
        
        if tag_content.startswith('voice='):
            # Voice switch
            voice_name = tag_content.split('=', 1)[1]
            active_voice = voice_name
            # Create event for voice switch (for tracking)
            output.append(Event(kind='voice_switch', ms=0))
        
        elif tag_content.startswith('pause:'):
            # Pause event
            try:
                pause_ms = int(tag_content.split(':', 1)[1])
                output.append(Event(kind='pause', ms=pause_ms))
            except (ValueError, IndexError):
                pass  # Invalid pause format, ignore
        
        elif tag_content == 'slow':
            active_pacing = 'slow'
        
        elif tag_content == '/slow':
            active_pacing = None
        
        elif tag_content == 'fast':
            active_pacing = 'fast'
        
        elif tag_content == '/fast':
            active_pacing = None
        
        elif tag_content == 'epigraph':
            in_epigraph = True
            output.append(Event(kind='epigraph_start', ms=0))
        
        elif tag_content == '/epigraph':
            in_epigraph = False
            output.append(Event(kind='epigraph_end', ms=0))
        
        elif tag_content == 'scene-break':
            output.append(Event(kind='scene_break', ms=900))  # Default 900ms pause
        
        last_end = end
    
    # Add remaining text after last tag
    if last_end < len(text):
        remaining_text = text[last_end:].strip()
        if remaining_text:
            segment = create_segment_from_text(
                remaining_text,
                position=len(output),
                voice_hint=active_voice,
                pacing=active_pacing,
                is_epigraph=in_epigraph,
            )
            output.append(segment)
    
    # Also handle standalone scene breaks (***)
    # Replace them with scene_break events
    final_output = []
    for item in output:
        if isinstance(item, Segment):
            # Check for *** in segment text
            if '***' in item.text:
                parts = item.text.split('***')
                for i, part in enumerate(parts):
                    if part.strip():
                        # Create new segment without ***
                        new_segment = create_segment_from_text(
                            part.strip(),
                            position=len(final_output),
                            voice_hint=item.meta.get('speaker_hint'),
                            pacing=item.meta.get('pacing'),
                            is_epigraph=item.meta.get('is_epigraph', False),
                        )
                        final_output.append(new_segment)
                    # Add scene break between parts (except after last)
                    if i < len(parts) - 1:
                        final_output.append(Event(kind='scene_break', ms=900))
            else:
                final_output.append(item)
        else:
            final_output.append(item)
    
    return final_output


def create_segment_from_text(
    text: str,
    position: int,
    voice_hint: Optional[str] = None,
    pacing: Optional[str] = None,
    is_epigraph: bool = False,
) -> Segment:
    """
    Create a Segment from text with metadata.
    
    Args:
        text: Segment text
        position: Position in document
        voice_hint: Optional voice hint
        pacing: Optional pacing hint
        is_epigraph: Whether this is part of an epigraph
        
    Returns:
        Segment object
    """
    from src.tts.segmenter import generate_segment_id, detect_dialogue, extract_speaker_hint
    
    segment_id = generate_segment_id(text, position, voice_hint)
    is_dialogue = detect_dialogue(text)
    speaker = voice_hint or extract_speaker_hint(text)
    
    return Segment(
        id=segment_id,
        text=text,
        meta={
            'is_dialogue': is_dialogue,
            'speaker_hint': speaker,
            'pacing': pacing,
            'is_epigraph': is_epigraph,
        }
    )

