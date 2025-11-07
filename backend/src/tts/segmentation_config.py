"""Segmentation configuration."""

from typing import Optional
from pathlib import Path
import json
import yaml


def get_default_config() -> dict:
    """
    Get default segmentation configuration.
    
    Returns:
        Dictionary with default config
    """
    return {
        'max_chars_per_breath': 200,
        'split_on_commas': True,
        'split_on_dashes': True,
        'split_on_semicolons': True,
    }


def load_config_from_file(config_path: Path) -> dict:
    """
    Load segmentation config from YAML or JSON file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Config dictionary
    """
    if not config_path.exists():
        return get_default_config()
    
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            try:
                data = yaml.safe_load(f)
            except ImportError:
                # Fallback to JSON if YAML not available
                data = json.load(f)
        else:
            data = json.load(f)
    
    # Merge with defaults
    config = get_default_config()
    config.update(data)
    
    return config


def save_config_to_file(config: dict, config_path: Path) -> None:
    """
    Save segmentation config to file.
    
    Args:
        config: Config dictionary
        config_path: Path to save config file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            try:
                yaml.dump(config, f, default_flow_style=False)
            except ImportError:
                # Fallback to JSON if YAML not available
                json.dump(config, f, indent=2)
        else:
            json.dump(config, f, indent=2)

