"""Unit tests for RoyalRoadClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.scraper.royal_road_client import RoyalRoadClient


class TestRoyalRoadClient:
    """Test cases for RoyalRoadClient."""
    
    def test_init_default_user_agent(self):
        """Test client initialization with default user agent."""
        with patch('src.scraper.royal_road_client.get_settings') as mock_settings:
            mock_settings.return_value.scraper_user_agent = "Test-Agent/1.0"
            client = RoyalRoadClient()
            
            assert client.session is not None
            assert client.session.headers['User-Agent'] == "Test-Agent/1.0"
    
    def test_init_custom_user_agent(self):
        """Test client initialization with custom user agent."""
        client = RoyalRoadClient(user_agent="Custom-Agent/2.0")
        
        assert client.session.headers['User-Agent'] == "Custom-Agent/2.0"
    
    @patch('src.scraper.royal_road_client.requests.Session.get')
    def test_get_success(self, mock_get):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html>content</html>"
        mock_get.return_value = mock_response
        
        client = RoyalRoadClient()
        response = client.get("https://example.com")
        
        assert response.status_code == 200
        mock_get.assert_called_once_with("https://example.com", timeout=30)
    
    @patch('src.scraper.royal_road_client.requests.Session.get')
    def test_get_failure(self, mock_get):
        """Test GET request failure."""
        mock_get.side_effect = requests.RequestException("Connection error")
        
        client = RoyalRoadClient()
        
        with pytest.raises(requests.RequestException):
            client.get("https://example.com")
    
    @patch('src.scraper.royal_road_client.BeautifulSoup')
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get')
    def test_get_soup(self, mock_get, mock_soup):
        """Test get_soup method."""
        mock_response = Mock()
        mock_response.content = b"<html>content</html>"
        mock_get.return_value = mock_response
        
        client = RoyalRoadClient()
        soup = client.get_soup("https://example.com")
        
        mock_get.assert_called_once_with("https://example.com", timeout=30)
        mock_soup.assert_called_once_with(b"<html>content</html>", "lxml")
    
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get_soup')
    def test_get_book_page(self, mock_get_soup):
        """Test get_book_page method."""
        mock_soup_obj = Mock()
        mock_get_soup.return_value = mock_soup_obj
        
        client = RoyalRoadClient()
        soup = client.get_book_page("https://royalroad.com/fiction/12345/book")
        
        mock_get_soup.assert_called_once_with("https://royalroad.com/fiction/12345/book")
        assert soup == mock_soup_obj
    
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get_soup')
    def test_get_table_of_contents_success(self, mock_get_soup):
        """Test get_table_of_contents with successful TOC."""
        mock_soup_obj = Mock()
        mock_get_soup.return_value = mock_soup_obj
        
        client = RoyalRoadClient()
        soup = client.get_table_of_contents("https://royalroad.com/fiction/12345/book")
        
        mock_get_soup.assert_called_once_with(
            "https://royalroad.com/fiction/12345/book/table-of-contents"
        )
        assert soup == mock_soup_obj
    
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get_book_page')
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get_soup')
    def test_get_table_of_contents_fallback(self, mock_get_soup, mock_get_book_page):
        """Test get_table_of_contents falls back to book page on error."""
        mock_get_soup.side_effect = requests.RequestException("Not found")
        mock_soup_obj = Mock()
        mock_get_book_page.return_value = mock_soup_obj
        
        client = RoyalRoadClient()
        soup = client.get_table_of_contents("https://royalroad.com/fiction/12345/book")
        
        assert soup == mock_soup_obj
        mock_get_book_page.assert_called_once_with("https://royalroad.com/fiction/12345/book")
    
    @patch('src.scraper.royal_road_client.RoyalRoadClient.get_soup')
    def test_get_chapter_page(self, mock_get_soup):
        """Test get_chapter_page method."""
        mock_soup_obj = Mock()
        mock_get_soup.return_value = mock_soup_obj
        
        client = RoyalRoadClient()
        soup = client.get_chapter_page("https://royalroad.com/fiction/12345/book/chapter/1")
        
        mock_get_soup.assert_called_once_with(
            "https://royalroad.com/fiction/12345/book/chapter/1"
        )
        assert soup == mock_soup_obj
    
    @patch('src.scraper.royal_road_client.requests.Session.get')
    def test_search(self, mock_get):
        """Test search method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html>search results</html>"
        mock_get.return_value = mock_response
        
        client = RoyalRoadClient()
        soup = client.search("test query")
        
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://www.royalroad.com/fictions/search"
        assert call_args[1]['params'] == {"q": "test query"}

