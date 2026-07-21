"""Text normalization for TTS generation.

Simplified version that applies all normalization steps for clean TTS output.
"""

import re
from typing import Optional

from src.text.lexicon import get_lexicon


class TextNormalizer:
    """Normalizes text for optimal TTS generation."""

    # Default acronym expansions
    ACRONYM_MAP = {
        'FC': 'F C',
        'PA': 'P A',
        'CA': 'C A',
        'U.S.': 'United States',
        'U.K.': 'United Kingdom',
        'Mr.': 'Mister',
        'Mrs.': 'Misses',
        'Dr.': 'Doctor',
        'vs.': 'versus',
        'etc.': 'etcetera',
    }

    def normalize(self, text: str) -> str:
        """
        Normalize raw text for TTS generation.

        Applies all normalization steps and returns cleaned text.

        Args:
            text: Raw input text

        Returns:
            Normalized text ready for chunking
        """
        # Apply normalization steps in order
        text = self.strip_leading_notes(text)
        text = self.normalize_scene_breaks(text)
        text = self.remove_drm_warnings(text)
        text = self.apply_lexicon(text)
        text = self.normalize_punctuation(text)
        text = self.normalize_acronyms(text)
        text = self.normalize_time_formats(text)
        text = self.normalize_numbers(text)
        text = self.normalize_dates(text)
        text = self.normalize_whitespace(text)

        return text

    # A leading author aside wrapped in square brackets, e.g.
    # "[This is long. Get coffee. Thanks for your support!]"
    _LEADING_NOTE = re.compile(r'^\s*\[[^\]]*\]\s*')
    # A leading bare chapter-number heading on its own line, e.g. "14." or "14"
    _LEADING_NUMBER = re.compile(r'^\s*\d+\.?[ \t]*(?:\n|$)')

    def strip_leading_notes(self, text: str) -> str:
        """Strip non-story preamble that leads a chapter before the prose begins.

        Removes author asides in [square brackets] and a bare chapter-number
        heading line (e.g. "14."). Only strips such blocks at the very start and
        stops at the first line of real prose, so brackets and numbers appearing
        mid-story are left untouched. Deterministic backstop for the LLM preamble
        check, which is non-deterministic and has let these through.
        """
        while True:
            stripped = self._LEADING_NOTE.sub('', text, count=1)
            stripped = self._LEADING_NUMBER.sub('', stripped, count=1)
            if stripped == text:
                break
            text = stripped
        return text.lstrip('\n')

    def apply_lexicon(self, text: str) -> str:
        """Respell hard-to-pronounce words (proper nouns, coined slang) so XTTS
        says them correctly. Driven by the configured pronunciation lexicon."""
        return get_lexicon().apply(text)

    def normalize_scene_breaks(self, text: str) -> str:
        """Normalize scene break markers to paragraph breaks."""
        # Common scene break patterns
        text = re.sub(r'\s*(?:\\\*){3,}\s*', '\n\n', text)
        text = re.sub(r'\s*\*{3,}\s*', '\n\n', text)
        text = re.sub(r'\s*-{3,}\s*', '\n\n', text)
        text = re.sub(r'\s*_{3,}\s*', '\n\n', text)
        text = re.sub(r'\s*(?:\*\s+){2,}\*\s*', '\n\n', text)
        text = re.sub(r'<hr\s*/?>', '\n\n', text, flags=re.IGNORECASE)
        return text

    def remove_drm_warnings(self, text: str) -> str:
        """Remove Royal Road and other DRM warning sentences."""
        patterns = [
            r'(?i)stolen\s+content\s+warning[^.]*royal\s+road[^.]*\.',
            r'(?i)taken\s+from\s+royal\s+road[^.]*\.',
            r'(?i)this\s+narrative\s+has\s+been\s+unlawfully\s+taken\s+from\s+royal\s+road[^.]*\.',
            r'(?i)if\s+you\s+see\s+it\s+on\s+amazon[^.]*please\s+report\s+it\.',
            r'(?i)this\s+tale\s+has\s+been\s+pilfered\s+from\s+royal\s+road[^.]*\.',
            r'(?i)if\s+you\s+stumble\s+upon\s+this\s+narrative\s+on\s+amazon[^.]*\.',
            r'(?i)if\s+you\s+discover\s+this\s+tale\s+on\s+amazon[^.]*\.',
            r'(?i)this\s+content\s+has\s+been\s+unlawfully\s+taken\s+from\s+royal\s+road[^.]*\.',
            r'(?i)unlawfully\s+taken\s+from\s+royal\s+road[^.]*\.',
            r'(?i)unauthorized\s+duplication[^.]*\.',
            r'(?i)this\s+novel\'?s\s+true\s+home\s+is\s+a\s+different\s+platform[^.]*\.',
            r'(?i)read\s+this\s+novel\s+on\s+royal\s+road\.',
            r'(?i)support\s+the\s+creativity\s+of\s+authors\s+by\s+visiting\s+royal\s+road[^.]*\.',
            r'(?i)this\s+tale\s+has\s+been\s+unlawfully\s+lifted[^.]*\.',
            r'(?i)the\s+author\'?s\s+narrative\s+has\s+been\s+misappropriated[^.]*\.',
            r'(?i)report\s+any\s+appearances\s+on\s+amazon\.',
            r'(?i)report\s+any\s+occurrences\.',
        ]

        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE)

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        return text

    def normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation for better TTS pronunciation."""
        # Convert straight quotes to curly quotes
        text = re.sub(r'(^|\s)"([^"]+)"', r'\1"\2"', text)
        text = re.sub(r'"([^"]+)"', r'"\1"', text)

        # Convert -- to em-dash
        text = re.sub(r'(\w)--(\w)', r'\1—\2', text)
        text = re.sub(r'\s--\s', ' — ', text)

        # Convert ... to ellipsis
        text = re.sub(r'\.{3,}', '…', text)

        # Collapse repeated punctuation
        text = re.sub(r'([!?])\1+', r'\1', text)

        # Remove markdown emphasis markers
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'\b_([^_]+)_\b', r'\1', text)

        # Numeric progression arrows: "£1,054 > £6,079" / "11,256>11,406" read as a
        # rising sequence rather than "greater than". Constrained to value contexts so
        # a stray ">" in prose is untouched. Runs before number/currency expansion, so
        # the flanks are still digits/currency symbols.
        text = re.sub(r'(?<=[\d%)])\s*>\s*(?=[£$€\d])', ', rising to ', text)

        # Slashes: "/week" -> " per week"; other word/value slashes read as a space
        # (compound/list separator) instead of the literal "slash".
        text = re.sub(r'/\s*(week|year|day|month|match|game)\b', r' per \1', text,
                      flags=re.IGNORECASE)
        text = re.sub(r'(?<=\w)\s*/\s*(?=\w)', ' ', text)

        # Drop orphan footnote asterisks (paired *emphasis* already removed above);
        # a bare "*" otherwise gets voiced as "asterisk" or glitches.
        text = text.replace('*', '')

        return text

    def normalize_acronyms(self, text: str) -> str:
        """Normalize acronyms by expanding from map."""
        for acronym, expansion in sorted(self.ACRONYM_MAP.items(), key=lambda x: -len(x[0])):
            pattern = r'\b' + re.escape(acronym) + r'\b'
            text = re.sub(pattern, expansion, text)
        return text

    def normalize_time_formats(self, text: str) -> str:
        """Normalize time formats to spoken form."""
        def time_replacer(match):
            hour = match.group(1)
            period = match.group(2).replace('.', '').upper()
            try:
                hour_words = self._number_to_words(int(hour))
                return f"{hour_words} {period[0]} {period[1]}"
            except ValueError:
                return match.group(0)

        text = re.sub(
            r'(\d+)\s+(a\.m\.|p\.m\.|am|pm|A\.M\.|P\.M\.|AM|PM)',
            time_replacer,
            text,
            flags=re.IGNORECASE
        )
        return text

    def normalize_numbers(self, text: str) -> str:
        """Normalize numbers to spoken form."""
        # Age normalization
        def age_replacer(match):
            try:
                return f"{self._number_to_words(int(match.group(1)))}-year-old"
            except ValueError:
                return match.group(0)
        text = re.sub(r'(\d+)-year-old', age_replacer, text)

        # Ordinal numbers
        def ordinal_replacer(match):
            try:
                return self._number_to_ordinal(int(match.group(1)))
            except ValueError:
                return match.group(0)
        text = re.sub(r'\b(\d{1,2})(st|nd|rd|th)\b', ordinal_replacer, text)

        # Currency + decimals share one amount speller. A magnitude suffix (k/m/bn)
        # places the unit word last ("£1.4m" -> "one point four million pounds"). A
        # MULTI-digit fraction with a suffix is multiplied out to an exact integer
        # instead of read digit-by-digit, because XTTS slurs digit runs ("one seven
        # six" -> "seventeen six"); so "£0.176m" -> "one hundred seventy-six thousand
        # pounds". Single-digit fractions ("point four") read fine and stay as-is.
        suffix_words = {'k': 'thousand', 'm': 'million', 'bn': 'billion', 'b': 'billion',
                        'thousand': 'thousand', 'million': 'million', 'billion': 'billion'}
        suffix_mult = {'k': 1000, 'm': 10**6, 'bn': 10**9, 'b': 10**9,
                       'thousand': 1000, 'million': 10**6, 'billion': 10**9}

        def amount_words(int_part, dec_part, suffix):
            suffix = (suffix or '').lower()
            if dec_part:
                mult = suffix_mult.get(suffix)
                pow10 = 10 ** len(dec_part)
                if mult and len(dec_part) >= 2 and (int(dec_part) * mult) % pow10 == 0:
                    scaled = int(int_part) * mult + int(dec_part) * mult // pow10
                    return self._number_to_words(scaled)
                words = self._number_to_words(int(int_part)) + ' point ' + self._spell_decimal(dec_part)
            else:
                words = self._number_to_words(int(int_part))
            if suffix in suffix_words:
                words += ' ' + suffix_words[suffix]
            return words

        def currency_replacer(match):
            currency_name = {'£': 'pounds', '$': 'dollars', '€': 'euros'}.get(match.group(1), 'units')
            try:
                words = amount_words(match.group(2).replace(',', ''), match.group(3), match.group(4))
            except ValueError:
                return match.group(0)
            return f"{words} {currency_name}"
        text = re.sub(
            r'([£$€])\s?(\d+(?:,\d{3})*)(?:\.(\d+))?(?:\s*(k|m|bn|thousand|million|billion))?\b',
            currency_replacer, text)

        # Decimals (non-currency): expand the whole value so the integer part isn't
        # left orphaned from its fraction. "147.8" -> "one hundred forty-seven point
        # eight". Runs after currency and before the large-integer rule (which would
        # otherwise grab just the "147").
        def decimal_replacer(match):
            try:
                return amount_words(match.group(1), match.group(2), match.group(3))
            except ValueError:
                return match.group(0)
        text = re.sub(r'\b(\d+)\.(\d+)(k|m|bn)?\b', decimal_replacer, text)

        # Large standalone numbers
        def number_replacer(match):
            num_str = match.group(0).replace(',', '')
            try:
                num = int(num_str)
                if num >= 100:
                    return self._number_to_words(num)
            except ValueError:
                pass
            return match.group(0)
        text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', number_replacer, text)
        text = re.sub(r'\b\d{3,}\b', number_replacer, text)

        return text

    def normalize_dates(self, text: str) -> str:
        """Normalize dates to spoken form."""
        def date_replacer(match):
            day = match.group(2)
            month = match.group(3)
            year = match.group(4)
            try:
                day_ordinal = self._number_to_ordinal(int(day))
                month_name = self._get_month_name(month)
                year_spoken = self._format_year(year)
                prefix = match.group(1) or ''
                return f"{prefix}{day_ordinal} of {month_name}, {year_spoken}"
            except ValueError:
                return match.group(0)

        text = re.sub(
            r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+)?(\d{1,2})\s+(\w+),\s+(\d{4})',
            date_replacer,
            text,
            flags=re.IGNORECASE
        )
        return text

    def normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving paragraphs."""
        text = text.replace('\t', ' ')
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # Helper methods

    def _number_to_words(self, n: int) -> str:
        """Convert number to words."""
        ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                'seventeen', 'eighteen', 'nineteen']
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']

        if n == 0:
            return 'zero'
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + ('-' + ones[n % 10] if n % 10 else '')
        if n < 1000:
            hundreds = ones[n // 100] + ' hundred'
            remainder = n % 100
            return hundreds + (' ' + self._number_to_words(remainder) if remainder else '')
        if n < 1000000:
            thousands = self._number_to_words(n // 1000) + ' thousand'
            remainder = n % 1000
            return thousands + (' ' + self._number_to_words(remainder) if remainder else '')
        if n < 1000000000:
            millions = self._number_to_words(n // 1000000) + ' million'
            remainder = n % 1000000
            return millions + (' ' + self._number_to_words(remainder) if remainder else '')
        if n < 1000000000000:
            billions = self._number_to_words(n // 1000000000) + ' billion'
            remainder = n % 1000000000
            return billions + (' ' + self._number_to_words(remainder) if remainder else '')
        return str(n)

    def _spell_decimal(self, digits: str) -> str:
        """Read a decimal fraction digit by digit: '176' -> 'one seven six'."""
        return ' '.join(self._number_to_words(int(d)) for d in digits)

    def _number_to_ordinal(self, n: int) -> str:
        """Convert number to ordinal."""
        ordinals = {
            1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth',
            6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth',
            11: 'eleventh', 12: 'twelfth', 13: 'thirteenth', 14: 'fourteenth',
            15: 'fifteenth', 16: 'sixteenth', 17: 'seventeenth', 18: 'eighteenth',
            19: 'nineteenth', 20: 'twentieth', 21: 'twenty-first', 22: 'twenty-second',
            23: 'twenty-third', 24: 'twenty-fourth', 25: 'twenty-fifth',
            26: 'twenty-sixth', 27: 'twenty-seventh', 28: 'twenty-eighth',
            29: 'twenty-ninth', 30: 'thirtieth', 31: 'thirty-first'
        }
        if n in ordinals:
            return ordinals[n]
        words = self._number_to_words(n)
        if words.endswith('y'):
            return words[:-1] + 'ieth'
        return words + 'th'

    def _get_month_name(self, month_abbr: str) -> str:
        """Convert month abbreviation to full name."""
        months = {
            'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
            'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
            'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
        }
        return months.get(month_abbr.lower()[:3], month_abbr)

    def _format_year(self, year: str) -> str:
        """Format year as spoken."""
        year_int = int(year)
        if year_int < 2000:
            century = year_int // 100
            remainder = year_int % 100
            century_words = self._number_to_words(century)
            if remainder == 0:
                return f"{century_words} hundred"
            return f"{century_words} {self._number_to_words(remainder)}"
        else:
            first_two = year_int // 100
            last_two = year_int % 100
            return f"{self._number_to_words(first_two)}-{self._number_to_words(last_two)}"


