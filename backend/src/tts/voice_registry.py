"""Voice registry system for multi-voice TTS."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Voice:
    """Voice definition for TTS synthesis."""
    name: str
    speaker_wav: str  # Path to reference audio file
    language: str = "en"


def load_voice_registry(config_path: Optional[Path] = None) -> Dict[str, Voice]:
    """
    Load voice registry from YAML or JSON file.
    
    Args:
        config_path: Optional path to voice registry config file
        
    Returns:
        Dictionary mapping voice names to Voice objects
    """
    # Get project root for resolving relative paths
    project_root = Path(__file__).parent.parent.parent.parent
    
    if config_path is None:
        # Try default location (relative to project root)
        default_path = project_root / "data" / "voices" / "default_voices.yaml"
        if default_path.exists():
            config_path = default_path
        else:
            # Return default registry with single narrator voice
            return get_default_registry()
    
    if not config_path.exists():
        return get_default_registry()
    
    # Load config file
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            try:
                data = yaml.safe_load(f)
            except ImportError:
                # Fallback to JSON if YAML not available
                data = json.load(f)
        else:
            data = json.load(f)
    
    # Convert to Voice objects
    registry = {}
    for name, voice_data in data.items():
        if isinstance(voice_data, dict):
            registry[name] = Voice(
                name=name,
                speaker_wav=voice_data.get('speaker_wav', ''),
                language=voice_data.get('language', 'en'),
            )
        else:
            # Simple format: just path
            registry[name] = Voice(
                name=name,
                speaker_wav=str(voice_data),
                language='en',
            )
    
    # Validate paths (project_root already set at top of function)
    for name, voice in registry.items():
        if not voice.speaker_wav:
            continue
        voice_path = Path(voice.speaker_wav)
        if not voice_path.is_absolute():
            # Resolve relative to project root (not config file parent)
            # This ensures paths like "data/voice_samples/..." work correctly
            voice_path = project_root / voice_path
        
        # Update with resolved path
        resolved_path = voice_path.resolve()
        if resolved_path.exists():
            voice.speaker_wav = str(resolved_path)
        else:
            logger.warning(f"Voice sample file not found: {resolved_path}")
            voice.speaker_wav = ''
    
    return registry


def get_default_registry() -> Dict[str, Voice]:
    """
    Get default voice registry with single narrator voice.
    
    Returns:
        Dictionary with default narrator voice
    """
    # Resolve relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    
    # Default narrator voice (p241 British male)
    default_speaker = project_root / "data" / "voice_samples" / "british_male" / "british_male_p241.wav"
    
    return {
        'narrator': Voice(
            name='narrator',
            speaker_wav=str(default_speaker.resolve()) if default_speaker.exists() else '',
            language='en',
        )
    }


def resolve_voice(
    name: str,
    registry: Dict[str, Voice],
    default: Optional[Voice] = None,
) -> Voice:
    """
    Resolve voice name to Voice object.
    
    Args:
        name: Voice name to resolve
        registry: Voice registry dictionary
        default: Default voice to use if name not found
        
    Returns:
        Resolved Voice object
    """
    if name in registry:
        return registry[name]
    
    if default:
        return default
    
    # Fallback to narrator if available
    if 'narrator' in registry:
        return registry['narrator']
    
    # Last resort: create a default voice
    return Voice(
        name='default',
        speaker_wav='',
        language='en',
    )


def save_voice_registry(registry: Dict[str, Voice], config_path: Path) -> None:
    """
    Save voice registry to file.
    
    Args:
        registry: Voice registry dictionary
        config_path: Path to save config file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    data = {}
    for name, voice in registry.items():
        data[name] = {
            'speaker_wav': voice.speaker_wav,
            'language': voice.language,
        }
    
    # Save to file
    with open(config_path, 'w', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            try:
                yaml.dump(data, f, default_flow_style=False)
            except ImportError:
                # Fallback to JSON if YAML not available
                json.dump(data, f, indent=2)
        else:
            json.dump(data, f, indent=2)

