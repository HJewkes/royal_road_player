"""Text formatting utilities."""

import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import Optional


class TextFormatter:
    """Format HTML content to Markdown text."""

    @staticmethod
    def html_to_text(html_content: str, preserve_paragraphs: bool = True, output_format: str = "markdown") -> str:
        """
        Convert HTML to Markdown or plain text.

        Args:
            html_content: HTML string to convert
            preserve_paragraphs: Whether to preserve paragraph breaks
            output_format: "markdown" or "plain" (default: "markdown")

        Returns:
            Markdown or plain text string
        """
        soup = BeautifulSoup(html_content, "lxml")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        if output_format == "markdown":
            # Convert to Markdown to preserve formatting
            # Use markdownify with options to preserve tables, lists, etc.
            # Note: markdownify doesn't allow both strip and convert, so we'll convert everything
            # and handle link text separately if needed
            markdown_text = md(
                str(soup),
                heading_style="ATX",  # Use # for headings
                bullets="-",  # Use - for lists
                convert=["p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i", "ul", "ol", "li", "table", "tr", "td", "th", "blockquote", "code", "pre", "a"],
            )
            
            # Clean up link formatting - markdownify creates [text](url), we want just text for TTS
            # Remove markdown links but keep the text
            markdown_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown_text)
            
            # Clean up excessive blank lines
            lines = markdown_text.split("\n")
            cleaned_lines = []
            prev_blank = False
            for line in lines:
                is_blank = not line.strip()
                if is_blank and prev_blank:
                    continue  # Skip consecutive blank lines
                cleaned_lines.append(line)
                prev_blank = is_blank
            
            text = "\n".join(cleaned_lines)
            
        else:
            # Fallback to plain text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

        if preserve_paragraphs:
            # Ensure paragraph breaks are preserved
            text = text.replace("\n\n\n", "\n\n")

        return text

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text of common artifacts while preserving Markdown formatting.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace but preserve Markdown structure
        lines = []
        for line in text.split("\n"):
            # Don't strip lines that are part of Markdown tables (start with |)
            if line.strip().startswith("|"):
                lines.append(line.rstrip())  # Only strip trailing whitespace
            elif line.strip().startswith("-") and len(line.strip()) > 1:
                # Markdown horizontal rule or list item - preserve
                lines.append(line.rstrip())
            elif line.strip().startswith("#"):
                # Markdown heading - preserve
                lines.append(line.rstrip())
            elif not line.strip():
                # Empty line - keep single blank lines
                if not lines or lines[-1].strip():
                    lines.append("")
            else:
                # Regular text - strip but preserve
                lines.append(line.strip())

        text = "\n".join(lines)

        # Remove common HTML artifacts
        text = text.replace("\xa0", " ")  # Non-breaking space
        text = text.replace("\u200b", "")  # Zero-width space
        text = text.replace("\u200c", "")  # Zero-width non-joiner
        text = text.replace("\u200d", "")  # Zero-width joiner

        # Clean up excessive blank lines (max 2 consecutive)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

