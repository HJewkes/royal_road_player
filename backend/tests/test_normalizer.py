"""Tests for the text normalizer's leading-preamble stripping."""

from src.text.normalizer import TextNormalizer


class TestStripLeadingNotes:
    """Tests for strip_leading_notes — the deterministic preamble backstop."""

    def setup_method(self):
        self.n = TextNormalizer()

    def test_strips_bracketed_author_note_and_number_heading(self):
        """The ch14 case: a leading [author note] and bare "14." heading are
        removed, but the story's opening date line is kept."""
        raw = (
            "[This is long. Get coffee. Thanks for your support!]\n\n"
            "14.\n\n"
            "Wednesday, December 20\n\n"
            "It was a dark, gloomy morning."
        )
        out = self.n.strip_leading_notes(raw)
        assert out.startswith("Wednesday, December 20")
        assert "Thanks for your support" not in out
        assert "14." not in out

    def test_strips_multiple_leading_notes(self):
        raw = "[note one]\n\n[note two]\n\n7.\n\nThe match began."
        out = self.n.strip_leading_notes(raw)
        assert out.startswith("The match began.")

    def test_keeps_mid_story_brackets_and_numbers(self):
        """Brackets and numbers that are not leading preamble must survive."""
        raw = "The score was 14. He wrote [redacted] on the board."
        out = self.n.strip_leading_notes(raw)
        assert out == raw

    def test_number_inside_sentence_is_not_treated_as_heading(self):
        """A leading line that starts with a number but is real prose is kept."""
        raw = "14 goals were scored that season.\n\nThen came the final."
        out = self.n.strip_leading_notes(raw)
        assert out.startswith("14 goals were scored")

    def test_clean_chapter_is_unchanged(self):
        raw = "Wednesday, December 20\n\nIt was a dark, gloomy morning."
        assert self.n.strip_leading_notes(raw) == raw
