"""Normalization rules configuration."""

from typing import Optional
from pathlib import Path
import json
import yaml


# Default acronym map
DEFAULT_ACRONYM_MAP = {
    'FC': 'F. C.',
    'U.K.': 'United Kingdom',
    'U.S.': 'United States',
    'U.S.A.': 'United States of America',
    'Dr.': 'Doctor',
    'Mr.': 'Mister',
    'Mrs.': 'Missus',
    'Ms.': 'Miss',
    'Prof.': 'Professor',
    'St.': 'Saint',
    'Ave.': 'Avenue',
    'Blvd.': 'Boulevard',
    'Rd.': 'Road',
}


def load_rules_from_file(config_path: Path) -> dict:
    """
    Load normalization rules from YAML or JSON file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Rules dictionary
    """
    if not config_path.exists():
        return get_default_rules()
    
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
    rules = get_default_rules()
    rules.update(data)
    
    return rules


def get_default_rules() -> dict:
    """
    Get default normalization rules.
    
    Returns:
        Dictionary with default rules
    """
    return {
        'acronym_map': DEFAULT_ACRONYM_MAP.copy(),
        'number_style': 'words',  # 'words' or 'digits'
        'date_style': 'spoken',   # 'spoken' or 'numeric'
        'preserve_paragraphs': True,
    }


def save_rules_to_file(rules: dict, config_path: Path) -> None:
    """
    Save normalization rules to file.
    
    Args:
        rules: Rules dictionary
        config_path: Path to save config file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            try:
                yaml.dump(rules, f, default_flow_style=False)
            except ImportError:
                # Fallback to JSON if YAML not available
                json.dump(rules, f, indent=2)
        else:
            json.dump(rules, f, indent=2)

