"""Unified configuration management for text processing."""

import json
from pathlib import Path
from typing import Optional
import yaml


class TextProcessingConfig:
    """Unified configuration for all text processing operations."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Optional path to config file (YAML or JSON)
        """
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from file or use defaults."""
        if self.config_path and self.config_path.exists():
            return self._load_from_file(self.config_path)
        return self.get_defaults()
    
    @staticmethod
    def _load_from_file(config_path: Path) -> dict:
        """Load config from YAML or JSON file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                try:
                    data = yaml.safe_load(f)
                except ImportError:
                    data = json.load(f)
            else:
                data = json.load(f)
        
        # Merge with defaults
        defaults = TextProcessingConfig.get_defaults()
        defaults.update(data)
        return defaults
    
    @staticmethod
    def get_defaults() -> dict:
        """Get default configuration."""
        return {
            # Normalization rules
            'acronym_map': {
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
            },
            'number_style': 'words',  # 'words' or 'digits'
            'date_style': 'spoken',   # 'spoken' or 'numeric'
            'preserve_paragraphs': True,
            
            # Segmentation config
            'max_chars_per_breath': 200,
            'split_on_commas': True,
            'split_on_dashes': True,
            'split_on_semicolons': True,
        }
    
    def save(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        path = config_path or self.config_path
        if not path:
            raise ValueError("No config path specified")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            if path.suffix in ['.yaml', '.yml']:
                try:
                    yaml.dump(self._config, f, default_flow_style=False)
                except ImportError:
                    json.dump(self._config, f, indent=2)
            else:
                json.dump(self._config, f, indent=2)
    
    @property
    def normalization_rules(self) -> dict:
        """Get normalization rules."""
        return {
            'acronym_map': self._config.get('acronym_map', {}),
            'number_style': self._config.get('number_style', 'words'),
            'date_style': self._config.get('date_style', 'spoken'),
            'preserve_paragraphs': self._config.get('preserve_paragraphs', True),
        }
    
    @property
    def segmentation_config(self) -> dict:
        """Get segmentation configuration."""
        return {
            'max_chars_per_breath': self._config.get('max_chars_per_breath', 200),
            'split_on_commas': self._config.get('split_on_commas', True),
            'split_on_dashes': self._config.get('split_on_dashes', True),
            'split_on_semicolons': self._config.get('split_on_semicolons', True),
        }
    
    def get(self, key: str, default=None):
        """Get config value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value) -> None:
        """Set config value."""
        self._config[key] = value

