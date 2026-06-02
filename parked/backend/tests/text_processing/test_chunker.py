"""Comprehensive test suite for text chunker with Chunkipy."""

import pytest

from src.text_processing.chunker import TextChunker


class TestBasicChunking:
    """Test basic chunking functionality."""
    
    def test_simple_sentences_under_limit(self):
        """Test that simple sentences under limit are kept intact."""
        chunker = TextChunker()
        text = "This is sentence one. This is sentence two. This is sentence three."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        assert len(chunks) > 0
        # Verify all content is preserved
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        # Verify no chunk exceeds limit
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250, f"Chunk exceeds limit: {len(chunk_text)} chars"
    
    def test_single_very_long_sentence_no_punctuation(self):
        """Test handling of extremely long sentence with no internal punctuation."""
        chunker = TextChunker()
        # Create a 500-char sentence with no punctuation
        text = "The quick brown fox jumped over the lazy dog " * 10 + "and then stopped."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        assert len(chunks) >= 2, "Long sentence should be split"
        # Verify all content is preserved
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        # Verify no chunk exceeds limit
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250, f"Chunk exceeds limit: {len(chunk_text)} chars"
    
    def test_long_sentence_with_commas(self):
        """Test that long sentences with commas are split intelligently."""
        chunker = TextChunker()
        text = ("The protagonist walked through the forest, "
                "noticed the birds singing overhead, "
                "felt the cool breeze on his face, "
                "heard the rustling leaves beneath his feet, "
                "and finally arrived at his destination, "
                "where he would begin his grand adventure.")
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Should split at commas if needed
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250


class TestPunctuationRetention:
    """Test that splitting characters are retained at chunk boundaries."""
    
    def test_period_retained_at_end(self):
        """Test that periods are kept at the end of chunks."""
        chunker = TextChunker()
        text = "Sentence one. Sentence two. Sentence three."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        assert text.count('.') == reconstructed.count('.'), "Periods should be preserved"
    
    def test_comma_retained_at_end(self):
        """Test that commas are kept when splitting."""
        chunker = TextChunker()
        text = "Part one, part two, part three, part four."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=30)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        assert text.count(',') == reconstructed.count(','), "Commas should be preserved"
    
    def test_exclamation_question_marks_retained(self):
        """Test that exclamation and question marks are preserved."""
        chunker = TextChunker()
        text = "What is this? It's amazing! Really? Yes!"
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        assert text.count('!') == reconstructed.count('!')
        assert text.count('?') == reconstructed.count('?')


class TestQuotesAndDialogue:
    """Test handling of quotes and dialogue."""
    
    def test_simple_dialogue(self):
        """Test basic dialogue preservation."""
        chunker = TextChunker()
        text = '"Hello there," she said. "How are you?" he replied.'
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        assert text.count('"') == reconstructed.count('"')
    
    def test_nested_quotes(self):
        """Test nested quotation marks."""
        chunker = TextChunker()
        text = 'He said, "She told me, \'Go away,\' and I left."'
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_long_dialogue_split(self):
        """Test that very long dialogue is split properly."""
        chunker = TextChunker()
        text = ('"This is a very long piece of dialogue that goes on and on '
                'about various topics including the weather, politics, and '
                'the nature of existence itself, continuing for quite some time '
                'without any break or pause," she explained carefully.')
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=150)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        # Should be split into multiple chunks
        assert len(chunks) >= 2


class TestWhitespaceHandling:
    """Test handling of whitespace and newlines."""
    
    def test_paragraph_breaks_preserved(self):
        """Test that paragraph breaks (\\n\\n) are preserved."""
        chunker = TextChunker()
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        assert text.count('\n') == reconstructed.count('\n')
    
    def test_single_newlines_preserved(self):
        """Test that single newlines are preserved."""
        chunker = TextChunker()
        text = "Line one\nLine two\nLine three"
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_leading_trailing_whitespace(self):
        """Test handling of leading/trailing whitespace."""
        chunker = TextChunker()
        text = "  Some text with spaces.  "
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        # Note: Chunkipy might strip some whitespace, so test for content preservation
        assert "Some text with spaces." in reconstructed


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = TextChunker()
        text = ""
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Should either return empty list or single empty chunk
        assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0].text_length == 0)
    
    def test_single_character(self):
        """Test handling of single character."""
        chunker = TextChunker()
        text = "a"
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        assert len(chunks) == 1
        reconstructed = text[chunks[0].text_start:chunks[0].text_end]
        assert reconstructed == text
    
    def test_only_whitespace(self):
        """Test handling of whitespace-only text."""
        chunker = TextChunker()
        text = "   \n\n   \n   "
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Whitespace-only chunks should be filtered or minimal
        assert len(chunks) <= 1
    
    def test_exact_limit_length(self):
        """Test text that is exactly at the character limit."""
        chunker = TextChunker()
        text = "a" * 250  # Exactly 250 characters
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        assert len(chunks) == 1
        assert chunks[0].text_length == 250
    
    def test_one_over_limit(self):
        """Test text that is one character over the limit."""
        chunker = TextChunker()
        text = "a" * 251  # 251 characters with NO whitespace
        
        # Should raise ValueError since there's no safe split point
        with pytest.raises(ValueError, match="no whitespace found"):
            chunker.chunk_by_paragraphs(text, max_chars=250)


class TestSpecialCharacters:
    """Test handling of special characters."""
    
    def test_unicode_characters(self):
        """Test handling of Unicode characters."""
        chunker = TextChunker()
        text = "This has émojis 🎉 and spëcial çharacters."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_multiple_punctuation(self):
        """Test handling of multiple punctuation marks."""
        chunker = TextChunker()
        text = "What?!? Really...? Yes!!!"
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_em_dash_and_ellipsis(self):
        """Test handling of em-dashes and ellipses."""
        chunker = TextChunker()
        text = "The story continues—without pause... or does it?"
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text


class TestMergeSmallChunks:
    """Test that small chunks are merged when possible."""
    
    def test_multiple_short_sentences_merged(self):
        """Test that multiple short sentences are merged into one chunk."""
        chunker = TextChunker()
        text = "Hi. Yes. No. OK. Sure. Fine. Good."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Should merge into fewer chunks rather than 7 separate ones
        assert len(chunks) < 7
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_merge_stops_at_limit(self):
        """Test that merging stops when limit would be exceeded."""
        chunker = TextChunker()
        # Create sentences that total just over 250 chars (actually 415 chars)
        text = ("This is a sentence. " * 20) + "Final sentence."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Should create multiple chunks
        assert len(chunks) >= 2
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250


class TestXTTSV2Compatibility:
    """Test compatibility with XTTS v2 requirements."""
    
    def test_respects_250_char_limit(self):
        """Test that no chunk exceeds the XTTS v2 250 character limit."""
        chunker = TextChunker()
        # Create various types of long text (with realistic whitespace)
        texts = [
            ("The quick brown fox " * 30),  # Repeated phrase with spaces
            ("This is a very long sentence that continues on and on "
             "with many clauses and subclauses and additional information "
             "that makes it exceed the character limit significantly.") * 3,
        ]
        
        for text in texts:
            chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
            
            for chunk in chunks:
                chunk_text = text[chunk.text_start:chunk.text_end]
                assert len(chunk_text) <= 250, (
                    f"Chunk exceeds XTTS v2 limit: {len(chunk_text)} chars"
                )
        
        # Test that text without whitespace raises an error
        with pytest.raises(ValueError, match="no whitespace found"):
            chunker.chunk_by_paragraphs("a" * 500, max_chars=250)
    
    def test_metadata_fields_present(self):
        """Test that chunks have all required metadata fields."""
        chunker = TextChunker()
        text = "Test sentence for metadata."
        
        chunks = chunker.chunk_by_paragraphs(
            text,
            book_id="test_book",
            chapter_id="test_chapter",
            default_voice_name="test_voice",
            default_speed=1.0,
        )
        
        assert len(chunks) > 0
        chunk = chunks[0]
        
        # Check all required fields exist
        assert chunk.book_id == "test_book"
        assert chunk.chapter_id == "test_chapter"
        assert chunk.voice_name is not None
        assert chunk.text_start >= 0
        assert chunk.text_end > chunk.text_start
        assert chunk.index == 1


class TestComplexRealWorldText:
    """Test with complex real-world text samples."""
    
    def test_novel_excerpt(self):
        """Test with a realistic novel excerpt."""
        chunker = TextChunker()
        text = """
"Where are you going?" she asked, her voice barely above a whisper.

He paused at the doorway, not turning back. "I don't know," he admitted. 
"Somewhere... anywhere but here."

The silence that followed was heavier than any words could have been. She 
watched as his shadow grew longer in the fading light, stretching across 
the worn wooden floor—the same floor where they'd danced just last summer, 
when everything seemed possible.

"Wait," she called out, but her voice broke on the word.
"""
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        
        # Should split into multiple reasonable chunks
        assert len(chunks) >= 2
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250
    
    def test_technical_text_with_numbers(self):
        """Test with technical text containing numbers and abbreviations."""
        chunker = TextChunker()
        text = ("The XTTS v2.0.1 system requires text chunks of max. 250 chars. "
                "According to the documentation (see pg. 42), this limit is enforced "
                "at the API level. Tests show 98.7% accuracy with proper chunking.")
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
    
    def test_mixed_dialogue_and_narration(self):
        """Test complex mixing of dialogue and narration."""
        chunker = TextChunker()
        text = """The protagonist entered the room. "Is anyone here?" he called out.
        
No response came from the darkness. He fumbled for the light switch, his 
heart pounding in his chest. Click. Nothing happened. "Great," he muttered 
under his breath. "Just great." The ancient manor house had clearly seen 
better days—probably around the time electricity was first invented, he 
thought wryly."""
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        reconstructed = ''.join([text[c.text_start:c.text_end] for c in chunks])
        assert reconstructed == text
        
        for chunk in chunks:
            chunk_text = text[chunk.text_start:chunk.text_end]
            assert len(chunk_text) <= 250


class TestContiguousCoverage:
    """Test that chunks provide contiguous coverage of the text."""
    
    def test_no_gaps_in_coverage(self):
        """Test that there are no gaps between chunks."""
        chunker = TextChunker()
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Check that chunks are contiguous
        for i in range(len(chunks) - 1):
            assert chunks[i].text_end == chunks[i + 1].text_start, (
                f"Gap found between chunk {i} and {i+1}"
            )
        
        # Check full coverage
        if chunks:
            assert chunks[0].text_start == 0
            assert chunks[-1].text_end == len(text)
    
    def test_no_overlaps(self):
        """Test that chunks don't overlap."""
        chunker = TextChunker()
        # Use realistic text with spaces (not solid block of letters)
        text = ("This is a test sentence. " * 30)  # ~750 chars that will be split
        
        chunks = chunker.chunk_by_paragraphs(text, max_chars=250)
        
        # Check for overlaps
        for i in range(len(chunks) - 1):
            assert chunks[i].text_end <= chunks[i + 1].text_start, (
                f"Overlap found between chunk {i} and {i+1}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

