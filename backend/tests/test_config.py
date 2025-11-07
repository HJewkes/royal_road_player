"""Tests for configuration module."""

import pytest
from src.utils.config import get_settings


def test_settings_load():
    """Test that settings load correctly."""
    settings = get_settings()
    assert settings is not None
    assert settings.web_port > 0
    assert settings.scraper_delay_seconds >= 0


def test_directories_created():
    """Test that required directories are created."""
    settings = get_settings()
    assert settings.data_dir.exists()
    assert settings.books_dir.exists()
    assert settings.log_dir.exists()

