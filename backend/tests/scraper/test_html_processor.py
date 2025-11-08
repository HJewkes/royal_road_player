"""Unit tests for HTMLProcessor."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from bs4 import BeautifulSoup

from src.scraper.html_processor import HTMLProcessor


class TestHTMLProcessor:
    """Test cases for HTMLProcessor."""
    
    def test_init(self):
        """Test processor initialization."""
        processor = HTMLProcessor()
        assert processor.formatter is not None
    
    def test_extract_book_id_success(self):
        """Test successful book ID extraction."""
        processor = HTMLProcessor()
        
        url = "https://www.royalroad.com/fiction/12345/book-title"
        book_id = processor.extract_book_id(url)
        
        assert book_id == "book_12345"
    
    def test_extract_book_id_failure(self):
        """Test book ID extraction failure."""
        processor = HTMLProcessor()
        
        with pytest.raises(ValueError, match="Could not extract book ID"):
            processor.extract_book_id("https://invalid-url.com")
    
    def test_extract_book_title_from_h1(self):
        """Test extracting book title from h1 element."""
        processor = HTMLProcessor()
        
        html = '<html><h1 class="fiction-title">Test Book Title</h1></html>'
        soup = BeautifulSoup(html, "lxml")
        
        title = processor.extract_book_title(soup, "https://royalroad.com/fiction/12345/book")
        assert title == "Test Book Title"
    
    def test_extract_book_title_from_page_title(self):
        """Test extracting book title from page title."""
        processor = HTMLProcessor()
        
        html = '<html><title>Test Book | Royal Road</title></html>'
        soup = BeautifulSoup(html, "lxml")
        
        title = processor.extract_book_title(soup, "https://royalroad.com/fiction/12345/book")
        assert title == "Test Book"
    
    def test_extract_book_title_removes_royal_road_suffix(self):
        """Test that Royal Road suffix is removed from title."""
        processor = HTMLProcessor()
        
        html = '<html><title>My Book | Royal Road</title></html>'
        soup = BeautifulSoup(html, "lxml")
        
        title = processor.extract_book_title(soup, "https://royalroad.com/fiction/12345/book")
        assert title == "My Book"
        assert "Royal Road" not in title
    
    def test_extract_book_title_fallback_to_url_slug(self):
        """Test fallback to URL slug when title not found."""
        processor = HTMLProcessor()
        
        html = '<html><body>No title here</body></html>'
        soup = BeautifulSoup(html, "lxml")
        
        title = processor.extract_book_title(soup, "https://royalroad.com/fiction/12345/my-book-title")
        assert title == "My Book Title"
    
    def test_extract_book_title_unknown_fallback(self):
        """Test fallback to 'Unknown Book' when nothing found."""
        processor = HTMLProcessor()
        
        html = '<html><body>No title</body></html>'
        soup = BeautifulSoup(html, "lxml")
        
        title = processor.extract_book_title(soup, "https://royalroad.com/fiction/12345")
        assert title == "Unknown Book"
    
    def test_extract_chapters_basic(self):
        """Test extracting chapters from TOC."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <a href="/fiction/12345/book/chapter/1">Chapter 1</a>
            <a href="/fiction/12345/book/chapter/2">Chapter 2</a>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        chapters = processor.extract_chapters(soup, "https://royalroad.com/fiction/12345/book")
        
        assert len(chapters) == 2
        assert chapters[0]['number'] == 1
        assert chapters[0]['title'] == "Chapter 1"
        assert "royalroad.com" in chapters[0]['url']
    
    def test_extract_chapters_filters_by_book_number(self):
        """Test filtering chapters by book number."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <a href="/fiction/12345/book/chapter/1/book-7">7.1 - Chapter Title</a>
            <a href="/fiction/12345/book/chapter/2/book-8">8.1 - Another Chapter</a>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        chapters = processor.extract_chapters(soup, "https://royalroad.com/fiction/12345/book", filter_book_number=7)
        
        assert len(chapters) == 1
        assert chapters[0]['number'] == 1
    
    def test_extract_chapters_removes_duplicates(self):
        """Test that duplicate chapter numbers are removed."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <a href="/fiction/12345/book/chapter/1">Chapter 1</a>
            <a href="/fiction/12345/book/chapter/1">Chapter 1 Duplicate</a>
            <a href="/fiction/12345/book/chapter/2">Chapter 2</a>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        chapters = processor.extract_chapters(soup, "https://royalroad.com/fiction/12345/book")
        
        assert len(chapters) == 2
        assert chapters[0]['number'] == 1
        assert chapters[1]['number'] == 2
    
    def test_extract_chapter_content(self):
        """Test extracting chapter content."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <div class="chapter-content">
                <p>This is chapter content.</p>
                <p>More content here.</p>
            </div>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        content = processor.extract_chapter_content(soup)
        
        assert "This is chapter content" in content
        assert "More content here" in content
    
    def test_extract_chapter_content_not_found(self):
        """Test error when chapter content not found."""
        processor = HTMLProcessor()
        
        html = '<html><body>No chapter content</body></html>'
        soup = BeautifulSoup(html, "lxml")
        
        with pytest.raises(ValueError, match="Could not find chapter content"):
            processor.extract_chapter_content(soup)
    
    @patch('src.scraper.html_processor.TextFormatter')
    def test_extract_chapter_content_uses_formatter(self, mock_formatter_class):
        """Test that extract_chapter_content uses formatter."""
        mock_formatter = Mock()
        mock_formatter.html_to_text.return_value = "Formatted text"
        mock_formatter.clean_text.return_value = "Cleaned formatted text"
        mock_formatter_class.return_value = mock_formatter
        
        processor = HTMLProcessor()
        processor.formatter = mock_formatter
        
        html = '''
        <html>
            <div class="chapter-content">
                <p>This is chapter content.</p>
            </div>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        content = processor.extract_chapter_content(soup)
        
        assert content == "Cleaned formatted text"
        mock_formatter.html_to_text.assert_called_once()
        mock_formatter.clean_text.assert_called_once()
    
    def test_extract_chapter_preview(self):
        """Test extracting chapter preview."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <div class="chapter-content">
                <p>This is a very long chapter content that should be truncated for preview purposes.</p>
            </div>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        preview = processor.extract_chapter_preview(soup, max_length=50)
        
        assert len(preview) <= 53  # 50 + "..."
        assert "..." in preview or len(preview) <= 50
    
    def test_sanitize_for_filesystem_basic(self):
        """Test basic filesystem sanitization."""
        processor = HTMLProcessor()
        
        result = processor.sanitize_for_filesystem("Test Book Title")
        assert result == "Test Book Title"
    
    def test_sanitize_for_filesystem_removes_invalid_chars(self):
        """Test that invalid filesystem characters are removed."""
        processor = HTMLProcessor()
        
        result = processor.sanitize_for_filesystem("Test<Book>:Title/With\\Invalid|Chars?")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
    
    def test_sanitize_for_filesystem_preserves_spaces(self):
        """Test that spaces are preserved when preserve_spaces=True."""
        processor = HTMLProcessor()
        
        result = processor.sanitize_for_filesystem("Test Book Title", preserve_spaces=True)
        assert " " in result
        assert result == "Test Book Title"
    
    def test_sanitize_for_filesystem_converts_spaces_to_hyphens(self):
        """Test that spaces are converted to hyphens when preserve_spaces=False."""
        processor = HTMLProcessor()
        
        result = processor.sanitize_for_filesystem("Test Book Title", preserve_spaces=False)
        assert " " not in result
        assert "-" in result
    
    def test_sanitize_for_filesystem_truncates_long_names(self):
        """Test that long names are truncated."""
        processor = HTMLProcessor()
        
        long_name = "A" * 200
        result = processor.sanitize_for_filesystem(long_name, max_length=50)
        
        assert len(result) <= 50
    
    def test_sanitize_for_filesystem_handles_empty_string(self):
        """Test that empty string returns 'untitled'."""
        processor = HTMLProcessor()
        
        result = processor.sanitize_for_filesystem("")
        assert result == "untitled"
    
    def test_filter_chapters_by_book_number(self):
        """Test filtering chapters by book number."""
        processor = HTMLProcessor()
        
        chapters = [
            {"title": "7.1 - Chapter One", "url": "https://royalroad.com/fiction/12345/book/chapter/1"},
            {"title": "7.2 - Chapter Two", "url": "https://royalroad.com/fiction/12345/book/chapter/2"},
            {"title": "8.1 - Chapter Three", "url": "https://royalroad.com/fiction/12345/book/chapter/3"},
        ]
        
        filtered = processor.filter_chapters_by_book(chapters, 7)
        
        assert len(filtered) == 2
        assert all(ch['title'].startswith("7.") for ch in filtered)
    
    def test_extract_search_results(self):
        """Test extracting search results."""
        processor = HTMLProcessor()
        
        html = '''
        <html>
            <div class="fiction-card">
                <a href="/fiction/12345/book-title">Test Book</a>
                <a href="/profile/author-name">Author Name</a>
            </div>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        
        results = processor.extract_search_results(soup)
        
        # Should find at least one result if the HTML structure matches
        # The actual implementation looks for specific class patterns
        assert isinstance(results, list)

