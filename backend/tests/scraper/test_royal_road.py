"""Tests for Royal Road scraper."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.scraper.royal_road import RoyalRoadScraper


class TestRoyalRoadScraper:
    """Test Royal Road scraper."""

    def test_extract_book_id(self):
        """Test book ID extraction from URL."""
        scraper = RoyalRoadScraper()
        
        # Test book URL
        url1 = "https://www.royalroad.com/fiction/12345/player-manager"
        assert scraper._extract_book_id(url1) == "book_12345"
        
        # Test chapter URL
        url2 = "https://www.royalroad.com/fiction/12345/player-manager/chapter/1/intro"
        assert scraper._extract_book_id(url2) == "book_12345"
        
        # Test invalid URL
        with pytest.raises(ValueError):
            scraper._extract_book_id("https://example.com")

    @patch("src.scraper.royal_road.requests.Session")
    def test_scrape_chapter_success(self, mock_session_class):
        """Test successful chapter scraping."""
        # Mock response
        mock_response = Mock()
        mock_response.content = b"""
        <html>
            <h1 class="chapter-title">Chapter 1: Test</h1>
            <div class="chapter-content">
                <p>This is test content.</p>
                <p>More content here.</p>
            </div>
        </html>
        """
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        scraper = RoyalRoadScraper()
        scraper.session = mock_session
        
        result = scraper.scrape_chapter("https://example.com/chapter/1", chapter_number=1)
        
        assert "title" in result
        assert "content" in result
        assert "word_count" in result
        assert result["word_count"] > 0

    def test_scraper_initialization(self):
        """Test scraper initialization."""
        scraper = RoyalRoadScraper()
        assert scraper.settings is not None
        assert scraper.formatter is not None
        assert scraper.metrics is not None

