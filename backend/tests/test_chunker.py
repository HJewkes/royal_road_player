"""Tests for text chunking, incl. the paragraph-split hallucination guard."""

from src.text.chunker import TextChunker, MAX_CHUNK_CHARS


def test_no_chunk_spans_a_paragraph_break():
    """A `."\\n\\nHeli` boundary inside a chunk makes XTTS hallucinate; each
    paragraph must become its own chunk even when the whole passage fits."""
    text = ('The Return of the King! Absolutely perfect."\n\n'
            'Heli eyed me sharply. "That\'s his favourite movie."')
    chunks = TextChunker().chunk(text)
    assert len(chunks) == 2
    assert all("\n\n" not in c.text for c in chunks)
    assert chunks[1].text.startswith("Heli")


def test_single_paragraph_unchanged():
    text = "A short single sentence that fits in one chunk."
    chunks = TextChunker().chunk(text)
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_long_paragraph_still_splits_on_char_limit():
    text = "Word. " * 80  # ~480 chars, one paragraph
    chunks = TextChunker().chunk(text)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)


def test_multiple_paragraphs_each_own_chunk():
    text = "First para.\n\nSecond para.\n\nThird para."
    chunks = TextChunker().chunk(text)
    assert [c.text for c in chunks] == ["First para.", "Second para.", "Third para."]


def test_blank_and_whitespace_paragraphs_dropped():
    text = "Real one.\n\n   \n\nReal two."
    chunks = TextChunker().chunk(text)
    assert [c.text for c in chunks] == ["Real one.", "Real two."]


def test_trailing_closing_quote_stripped():
    """A trailing `."` triggers end-of-chunk hallucination; the quote is dropped."""
    text = 'He said, "I get the message."'
    chunks = TextChunker().chunk(text)
    assert chunks[0].text == 'He said, "I get the message.'


def test_internal_quotes_preserved():
    text = 'She said "hello" and left.'
    chunks = TextChunker().chunk(text)
    assert chunks[0].text == 'She said "hello" and left.'  # only trailing stripped


def test_curly_trailing_quote_stripped():
    text = "It ended there.”"
    chunks = TextChunker().chunk(text)
    assert chunks[0].text == "It ended there."
