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


class TestCurrencyNormalization:
    """currency_replacer must expand decimals/suffixes and put the unit word last."""

    def setup_method(self):
        self.n = TextNormalizer()

    def test_decimal_million_suffix(self):
        assert self.n.normalize_numbers("£1.4m") == "one point four million pounds"

    def test_thousand_suffix(self):
        assert self.n.normalize_numbers("£900k") == "nine hundred thousand pounds"

    def test_spelled_out_million_word(self):
        assert self.n.normalize_numbers("£2 million") == "two million pounds"

    def test_plain_thousands_with_comma(self):
        assert self.n.normalize_numbers("£50,000") == "fifty thousand pounds"

    def test_multidigit_fraction_multiplied_out_not_read_digit_by_digit(self):
        # "one seven six" gets slurred by XTTS ("seventeen six"); multiply out instead.
        assert self.n.normalize_numbers("£0.176m") == "one hundred seventy-six thousand pounds"

    def test_two_digit_fraction_suffix_multiplied_out(self):
        assert self.n.normalize_numbers("£0.28m") == "two hundred eighty thousand pounds"

    def test_multimillion_with_commas(self):
        assert self.n.normalize_numbers("£4,163,432") == (
            "four million one hundred sixty-three thousand four hundred thirty-two pounds"
        )

    def test_dollars_and_euros(self):
        assert self.n.normalize_numbers("$5.24m") == "five million two hundred forty thousand dollars"
        assert self.n.normalize_numbers("€3k") == "three thousand euros"

    def test_single_digit_fraction_stays_point_form(self):
        # Single-digit fractions read fine as "point four" — keep them natural.
        assert self.n.normalize_numbers("£1.4m") == "one point four million pounds"


class TestNumberWordsScale:
    """_number_to_words must reach millions and billions (was capped below a million)."""

    def setup_method(self):
        self.n = TextNormalizer()

    def test_millions(self):
        assert self.n._number_to_words(4000000) == "four million"

    def test_billions(self):
        assert self.n._number_to_words(2000000000) == "two billion"


class TestProgressionAndSlashAndAsterisk:
    def setup_method(self):
        self.n = TextNormalizer()

    def test_progression_arrow_becomes_rising_to(self):
        out = self.n.normalize_punctuation("£1,054 > £6,079")
        assert ">" not in out and ", rising to " in out

    def test_glued_progression_arrow(self):
        out = self.n.normalize_punctuation("11,256>11,406")
        assert out == "11,256, rising to 11,406"

    def test_progression_end_to_end(self):
        assert self.n.normalize("£1,054 > £6,079") == (
            "one thousand fifty-four pounds, rising to six thousand seventy-nine pounds"
        )

    def test_slash_week_becomes_per_week(self):
        assert self.n.normalize_punctuation("£9,800/week").endswith("per week")

    def test_compound_slash_becomes_space(self):
        assert self.n.normalize_punctuation("commercial/retail") == "commercial retail"

    def test_orphan_footnote_asterisk_removed(self):
        out = self.n.normalize_punctuation("Manager Ranking*: 18")
        assert out == "Manager Ranking: 18"

    def test_standalone_asterisk_line_stripped(self):
        assert "*" not in self.n.normalize_punctuation("* In the English leagues")

    def test_greater_than_in_prose_untouched(self):
        # No digit/currency on both sides -> not a progression, left alone.
        out = self.n.normalize_punctuation("bigger > smaller")
        assert out == "bigger > smaller"


class TestDecimalNormalization:
    """Decimals must expand fully, not leave the fraction orphaned from the integer."""

    def setup_method(self):
        self.n = TextNormalizer()

    def test_decimal_over_one_hundred(self):
        # The reported bug: "147.8" -> "one hundred forty-seven.8".
        assert self.n.normalize_numbers("147.8") == "one hundred forty-seven point eight"

    def test_decimal_in_sentence(self):
        assert self.n.normalize_numbers("We were 147.8 but we played worse") == (
            "We were one hundred forty-seven point eight but we played worse"
        )

    def test_small_decimal(self):
        assert self.n.normalize_numbers("3.5") == "three point five"

    def test_decimal_with_magnitude_suffix(self):
        assert self.n.normalize_numbers("3.1m") == "three point one million"  # single digit
        assert self.n.normalize_numbers("0.28m") == "two hundred eighty thousand"  # multi-digit -> integer

    def test_percentage_decimal_keeps_percent(self):
        assert self.n.normalize_numbers("1.39%") == "one point three nine%"

    def test_currency_decimal_still_correct(self):
        # Currency runs first; the decimal rule must not touch an already-expanded amount.
        assert self.n.normalize_numbers("£1.4m") == "one point four million pounds"


class TestStandaloneYears:
    """A bare 1100-2099 in prose reads as a year, not a cardinal."""

    def setup_method(self):
        self.n = TextNormalizer()

    def test_since_year_reads_as_year(self):
        out = self.n.normalize("like they have been doing since 1872. What's the most 1872 name")
        assert out == (
            "like they have been doing since eighteen seventy-two. "
            "What's the most eighteen seventy-two name"
        )

    def test_quoted_year_reads_as_year(self):
        out = self.n.normalize('"1902," she said. "Hirst and Rhodes')
        assert out.startswith('"nineteen oh two," she said.')

    def test_sentence_initial_year_reads_as_year(self):
        out = self.n.normalize("1901 was Tottenham Hotspur as a non-league")
        assert out == "nineteen oh one was Tottenham Hotspur as a non-league"

    def test_year_before_apostrophe_word_reads_as_year(self):
        out = self.n.normalize("every year since 1872, Gangster's Paradise")
        assert out == "every year since eighteen seventy-two, Gangster's Paradise"

    def test_year_at_sentence_end_reads_as_year(self):
        assert self.n.normalize("Max: Joe Royle, 1995.") == "Max: Joe Royle, nineteen ninety-five."

    def test_year_spellings_at_century_edges(self):
        cases = {
            "1100": "eleven hundred",
            "1900": "nineteen hundred",
            "1905": "nineteen oh five",
            "2000": "two thousand",
            "2007": "two thousand seven",
            "2019": "twenty-nineteen",
            "2099": "twenty-ninety-nine",
        }
        for digits, spoken in cases.items():
            assert self.n.normalize_numbers(f"in {digits} it") == f"in {spoken} it"

    def test_money_is_not_a_year(self):
        assert self.n.normalize_numbers("$1995") == "one thousand nine hundred ninety-five dollars"

    def test_measurement_is_not_a_year(self):
        assert self.n.normalize_numbers("1995 kg") == "one thousand nine hundred ninety-five kg"
        assert self.n.normalize_numbers("1995 miles") == "one thousand nine hundred ninety-five miles"

    def test_percentage_is_not_a_year(self):
        assert self.n.normalize_numbers("1995%") == "one thousand nine hundred ninety-five%"

    def test_thousands_separator_is_not_a_year(self):
        assert self.n.normalize_numbers("1,995") == "one thousand nine hundred ninety-five"

    def test_part_of_larger_number_is_not_a_year(self):
        assert self.n.normalize_numbers("21995") == "twenty-one thousand nine hundred ninety-five"
        assert self.n.normalize_numbers("1995.5") == "one thousand nine hundred ninety-five point five"

    def test_outside_year_range_stays_cardinal(self):
        assert self.n.normalize_numbers("1050 and 2100") == (
            "one thousand fifty and two thousand one hundred"
        )

    def test_bare_count_defaults_to_year(self):
        # The normalizer has no count context, so a bare in-range integer is a year.
        assert self.n.normalize_numbers("1500 men") == "fifteen hundred men"

    def test_full_date_keeps_year_spelling(self):
        assert self.n.normalize_dates("Monday, 5 May, 1995") == (
            "Monday, fifth of May, nineteen ninety-five"
        )
