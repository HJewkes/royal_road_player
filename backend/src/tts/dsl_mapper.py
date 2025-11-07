"""Map DSL output to XTTS synthesis actions."""

from typing import List, Union, Dict, Optional
from pathlib import Path

from src.tts.segmenter import Segment
from src.tts.dsl_parser import Event
from src.tts.voice_registry import Voice, resolve_voice


def map_dsl_to_segments(
    dsl_output: List[Union[Segment, Event]],
    voice_registry: Dict[str, Voice],
    default_voice: Voice,
) -> List[Union[Segment, Event]]:
    """
    Map DSL output to segments with voice assignments.
    
    This function:
    - Resolves voice names to Voice objects
    - Adjusts segmentation based on pacing hints
    - Preserves pause and scene break events
    
    Args:
        dsl_output: List of Segment and Event objects from DSL parser
        voice_registry: Voice registry dictionary
        default_voice: Default voice to use
        
    Returns:
        List of Segment and Event objects with voice assignments
    """
    mapped_output = []
    current_voice = default_voice
    
    for item in dsl_output:
        if isinstance(item, Event):
            # Preserve events as-is
            mapped_output.append(item)
            
            # Handle voice switch events
            if item.kind == 'voice_switch':
                # Voice was switched in DSL, but we need to track it
                # The actual voice assignment happens when processing segments
                pass
        
        elif isinstance(item, Segment):
            # Determine voice for this segment
            voice_name = item.meta.get('speaker_hint')
            if voice_name:
                # Try to resolve voice from registry
                resolved_voice = resolve_voice(voice_name, voice_registry, default_voice)
            else:
                # Use current voice (from [voice=Name] tag)
                resolved_voice = current_voice
            
            # Update segment metadata with voice info
            item.meta['voice'] = resolved_voice.name
            item.meta['speaker_wav'] = resolved_voice.speaker_wav
            item.meta['language'] = resolved_voice.language
            
            # Adjust segmentation based on pacing
            if item.meta.get('pacing') == 'slow':
                # For slow pacing, we could split into smaller segments
                # For now, just mark it in metadata
                item.meta['pacing_adjustment'] = 'slow'
            elif item.meta.get('pacing') == 'fast':
                item.meta['pacing_adjustment'] = 'fast'
            
            mapped_output.append(item)
    
    return mapped_output


def apply_pacing_to_segments(
    segments: List[Segment],
    pacing: Optional[str] = None,
) -> List[Segment]:
    """
    Apply pacing adjustments to segments.
    
    For slow pacing: split into smaller segments
    For fast pacing: combine segments where possible
    
    Args:
        segments: List of segments
        pacing: Pacing hint ('slow', 'fast', or None)
        
    Returns:
        List of adjusted segments
    """
    if pacing is None:
        return segments
    
    if pacing == 'slow':
        # Split long segments into smaller ones
        adjusted = []
        for seg in segments:
            if len(seg.text) > 150:  # Split if longer than 150 chars
                # Simple split at commas or periods
                parts = []
                current = ''
                for char in seg.text:
                    current += char
                    if char in ',.' and len(current) > 80:
                        parts.append(current.strip())
                        current = ''
                if current.strip():
                    parts.append(current.strip())
                
                # Create new segments
                for i, part in enumerate(parts):
                    new_seg = Segment(
                        id=f"{seg.id}_{i}",
                        text=part,
                        meta=seg.meta.copy(),
                    )
                    adjusted.append(new_seg)
            else:
                adjusted.append(seg)
        return adjusted
    
    elif pacing == 'fast':
        # Combine short segments
        adjusted = []
        current = None
        for seg in segments:
            if current is None:
                current = seg
            elif len(current.text) + len(seg.text) < 300:
                # Combine segments
                current = Segment(
                    id=f"{current.id}_{seg.id}",
                    text=f"{current.text} {seg.text}",
                    meta=current.meta.copy(),
                )
            else:
                adjusted.append(current)
                current = seg
        if current:
            adjusted.append(current)
        return adjusted
    
    return segments

