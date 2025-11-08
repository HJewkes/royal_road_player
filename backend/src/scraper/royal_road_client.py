"""HTTP client for Royal Road web interactions."""

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class RoyalRoadClient:
    """HTTP client for interacting with Royal Road website."""
    
    def __init__(self, user_agent: Optional[str] = None):
        """
        Initialize Royal Road client.
        
        Args:
            user_agent: Optional custom user agent (defaults to settings)
        """
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or self.settings.scraper_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
    
    def get(self, url: str, timeout: int = 30) -> requests.Response:
        """
        Make a GET request to Royal Road.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise
    
    def get_soup(self, url: str, timeout: int = 30) -> BeautifulSoup:
        """
        Fetch URL and parse as BeautifulSoup.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            BeautifulSoup object
            
        Raises:
            requests.RequestException: If request fails
        """
        response = self.get(url, timeout=timeout)
        return BeautifulSoup(response.content, "lxml")
    
    def get_book_page(self, book_url: str) -> BeautifulSoup:
        """
        Get book page HTML.
        
        Args:
            book_url: URL to Royal Road book page
            
        Returns:
            BeautifulSoup object
        """
        return self.get_soup(book_url)
    
    def get_table_of_contents(self, book_url: str) -> BeautifulSoup:
        """
        Get table of contents page HTML.
        
        Args:
            book_url: URL to Royal Road book page
            
        Returns:
            BeautifulSoup object (falls back to book page if TOC doesn't exist)
        """
        toc_url = book_url.rstrip("/") + "/table-of-contents"
        try:
            return self.get_soup(toc_url)
        except requests.RequestException:
            # Fall back to main book page
            logger.debug(f"TOC not found, using book page: {book_url}")
            return self.get_book_page(book_url)
    
    def get_chapter_page(self, chapter_url: str) -> BeautifulSoup:
        """
        Get chapter page HTML.
        
        Args:
            chapter_url: URL to Royal Road chapter page
            
        Returns:
            BeautifulSoup object
        """
        return self.get_soup(chapter_url)
    
    def get_series_page(self, series_url: str) -> BeautifulSoup:
        """
        Get series page HTML.
        
        Args:
            series_url: URL to Royal Road series page
            
        Returns:
            BeautifulSoup object
        """
        return self.get_soup(series_url)
    
    def search(self, query: str) -> BeautifulSoup:
        """
        Search Royal Road for books.
        
        Args:
            query: Search query (book title or author)
            
        Returns:
            BeautifulSoup object of search results page
        """
        search_url = f"https://www.royalroad.com/fictions/search"
        params = {"q": query}
        response = self.session.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.content, "lxml")

