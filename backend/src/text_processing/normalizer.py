"""Text normalization for TTS generation - Object-Oriented Implementation."""

import re
from typing import Optional
from pathlib import Path

from src.text_processing.config import TextProcessingConfig


class TextNormalizer:
    """Normalizes text for optimal TTS generation."""
    
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        """
        Initialize text normalizer.
        
        Args:
            config: Optional TextProcessingConfig instance (creates default if not provided)
        """
        self.config = config or TextProcessingConfig()
        self.rules = self.config.normalization_rules
    
    def normalize(self, text: str) -> list[str]:
        """
        Normalize raw text for TTS generation.
        
        Applies all normalization steps and returns list of paragraphs.
        
        Args:
            text: Raw input text
            
        Returns:
            List of normalized paragraphs
        """
        # Apply normalization steps in order
        text = self.normalize_scene_breaks(text)
        text = self.normalize_punctuation(text)
        text = self.normalize_acronyms(text)
        text = self.normalize_numbers(text)
        text = self.normalize_dates(text)
        text = self.normalize_s_sound_cutoff(text)  # Workaround for XTTS v2 "s" sound cutoff
        text = self.normalize_whitespace(text)
        
        # Split into paragraphs
        if self.rules.get('preserve_paragraphs', True):
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        else:
            paragraphs = [text] if text.strip() else []
        
        return paragraphs
    
    def normalize_scene_breaks(self, text: str) -> str:
        """
        Normalize scene break markers to appropriate whitespace pauses.
        
        Converts common scene break markers (***, ---, ___, etc.) to multiple
        paragraph breaks, which will be detected by the chunker and marked
        with appropriate pause metadata.
        
        Args:
            text: Raw input text
            
        Returns:
            Text with scene break markers replaced by paragraph breaks
        """
        # Common scene break patterns (3+ repeated characters, possibly on their own line)
        # Match: ***, ---, ___, * * *, - - -, etc.
        # Also handle escaped versions: \*\*\*, \\*\\*\\*, etc.
        
        # Pattern 1: Literal backslash-asterisk sequences (e.g., \*\*\*)
        # Matches: \*\*\*, \\*\\*\\*, etc. (literal backslashes in text)
        # Match with optional surrounding whitespace/newlines
        # Note: In Python strings, \\\* matches a literal backslash followed by asterisk
        text = re.sub(r'\s*(?:\\\*){3,}\s*', '\n\n', text)  # \*\*\*, \*\*\*\*, etc.
        text = re.sub(r'\s*(?:\\-){3,}\s*', '\n\n', text)   # \-\-\-, \-\-\-\-, etc.
        text = re.sub(r'\s*(?:\\_){3,}\s*', '\n\n', text)   # \_\_\_, \_\_\_\_, etc.
        
        # Pattern 2: Unescaped scene break markers (3+ repeated chars)
        # Matches: ***, ---, ___, ****, etc. (with optional surrounding whitespace)
        text = re.sub(r'\s*\*{3,}\s*', '\n\n', text)   # Asterisks
        text = re.sub(r'\s*-{3,}\s*', '\n\n', text)    # Dashes
        text = re.sub(r'\s*_{3,}\s*', '\n\n', text)    # Underscores
        
        # Pattern 3: Spaced markers (e.g., * * *, - - -)
        text = re.sub(r'\s*(?:\*\s+){2,}\*\s*', '\n\n', text)  # * * *
        text = re.sub(r'\s*(?:-\s+){2,}-\s*', '\n\n', text)    # - - -
        text = re.sub(r'\s*(?:_\s+){2,}_\s*', '\n\n', text)    # _ _ _
        
        # Pattern 4: Horizontal rules (HTML-style, though less common in plain text)
        text = re.sub(r'<hr\s*/?>', '\n\n', text, flags=re.IGNORECASE)
        
        return text
    
    def normalize_punctuation(self, text: str) -> str:
        """
        Normalize punctuation for better TTS pronunciation.
        
        - Convert straight quotes to curly quotes
        - Convert -- to em-dash —
        - Collapse repeated punctuation
        - Convert ... to ellipsis …
        """
        # Convert straight quotes to curly quotes
        text = re.sub(r'(^|\s)"([^"]+)"', r'\1"\2"', text)
        text = re.sub(r'"([^"]+)"', r'"\1"', text)
        
        # Convert -- to em-dash (but not in URLs or code)
        text = re.sub(r'(\w)--(\w)', r'\1—\2', text)
        text = re.sub(r'\s--\s', ' — ', text)
        text = re.sub(r'^--\s', '— ', text)
        text = re.sub(r'\s--$', ' —', text)
        
        # Convert ... to ellipsis
        text = re.sub(r'\.{3,}', '…', text)
        
        # Collapse repeated punctuation (but preserve ellipsis)
        text = re.sub(r'([!?])\1+', r'\1', text)
        
        return text
    
    def normalize_acronyms(self, text: str) -> str:
        """Expand acronyms according to rule map."""
        acronym_map = self.rules.get('acronym_map', {})
        if not acronym_map:
            return text
        
        # Sort by length (longest first) to avoid partial matches
        sorted_acronyms = sorted(acronym_map.items(), key=lambda x: len(x[0]), reverse=True)
        
        for acronym, expansion in sorted_acronyms:
            # Word boundary check - only match whole words
            pattern = r'\b' + re.escape(acronym) + r'\b'
            text = re.sub(pattern, expansion, text)
        
        return text
    
    def normalize_numbers(self, text: str) -> str:
        """
        Normalize numbers to spoken form.
        
        Handles:
        - Ages: 28-year-old → twenty-eight-year-old
        - Currency: £800,000 → eight hundred thousand pounds
        - Simple numbers: 14 → fourteen
        """
        number_style = self.rules.get('number_style', 'words')
        
        # Age normalization: X-year-old → X-year-old (spoken)
        def age_replacer(match):
            num = match.group(1)
            try:
                num_int = int(num)
                words = self._number_to_words(num_int)
                return f"{words}-year-old"
            except (ValueError, AttributeError):
                return match.group(0)
        
        text = re.sub(r'(\d+)-year-old', age_replacer, text)
        
        # Currency normalization
        if number_style == "words":
            def currency_replacer(match):
                symbol = match.group(1)  # £, $, etc.
                amount = match.group(2).replace(',', '')
                try:
                    amount_int = int(amount)
                    words = self._number_to_words(amount_int)
                    currency_name = self._get_currency_name(symbol)
                    return f"{words} {currency_name}"
                except (ValueError, AttributeError):
                    return match.group(0)
            
            text = re.sub(r'([£$€])([\d,]+)', currency_replacer, text)
        
        return text
    
    def normalize_dates(self, text: str) -> str:
        """
        Normalize dates to spoken form.
        
        Patterns:
        - 4 Feb, 2024 → the fourth of February, twenty-twenty-four
        - 04/02/2024 → the fourth of February, twenty-twenty-four
        """
        date_style = self.rules.get('date_style', 'spoken')
        if date_style != "spoken":
            return text
        
        # Pattern: Day Month, Year (e.g., "4 Feb, 2024")
        def date_replacer1(match):
            day = match.group(1)
            month = match.group(2)
            year = match.group(3)
            
            try:
                day_int = int(day)
                day_ordinal = self._number_to_ordinal(day_int)
                month_name = self._get_month_name(month)
                year_spoken = self._format_year(year)
                return f"{day_ordinal} of {month_name}, {year_spoken}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        text = re.sub(r'(\d{1,2})\s+(\w+),\s+(\d{4})', date_replacer1, text, flags=re.IGNORECASE)
        
        # Pattern: DD/MM/YYYY or MM/DD/YYYY (assume DD/MM/YYYY for now)
        def date_replacer2(match):
            day = match.group(1)
            month = match.group(2)
            year = match.group(3)
            
            try:
                day_int = int(day)
                month_int = int(month)
                day_ordinal = self._number_to_ordinal(day_int)
                month_name = self._get_month_name_by_number(month_int)
                year_spoken = self._format_year(year)
                return f"{day_ordinal} of {month_name}, {year_spoken}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        text = re.sub(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_replacer2, text)
        
        return text
    
    def normalize_s_sound_cutoff(self, text: str) -> str:
        """
        Workaround for XTTS v2 cutting off "s" sounds at sentence endings.
        
        XTTS v2 has a known issue where fricative sounds (like "s") at the end
        of sentences can be cut off prematurely. This adds a small padding
        after sentences ending in words with "s" sounds to give the model
        more "room" to complete the sound.
        
        The padding is minimal (just an extra space) to avoid affecting
        the natural flow of speech while giving XTTS time to complete the sound.
        
        Args:
            text: Input text
            
        Returns:
            Text with minimal padding added after sentences ending in "s" sounds
        """
        # Only apply if enabled (default: True)
        if not self.rules.get('fix_s_sound_cutoff', True):
            return text
        
        # Pattern: Sentence ending with word ending in "s" followed by punctuation
        # We add a small amount of whitespace padding to give XTTS more time
        # to complete the "s" sound without affecting the spoken output
        
        def add_padding(match):
            """Add minimal padding after sentence ending in 's' sound."""
            # Get the matched text (word ending in s + optional space + punctuation + whitespace)
            matched = match.group(0)
            # Add an extra space to give XTTS room to complete the "s" sound
            # This is minimal and won't affect the spoken output noticeably
            return matched + ' '
        
        # Match sentences ending with words ending in "s"
        # Pattern breakdown:
        # - \b\w+[sS] : Word ending in 's' or 'S' (whole word boundary)
        # - \s* : Optional whitespace (handles "words ." case)
        # - [.!?] : Sentence-ending punctuation
        # - \s* : Optional trailing whitespace
        # This handles both "words." and "words ." cases
        text = re.sub(r'\b\w+[sS]\s*[.!?]\s*', add_padding, text)
        
        return text
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace while preserving structure.
        
        - Collapse excess spaces
        - Preserve paragraph breaks (double newlines)
        - Normalize tabs to spaces
        """
        preserve_paragraphs = self.rules.get('preserve_paragraphs', True)
        
        # Normalize tabs to spaces
        text = text.replace('\t', ' ')
        
        # Collapse multiple spaces to single space (within lines)
        text = re.sub(r' +', ' ', text)
        
        if preserve_paragraphs:
            # Normalize 3+ newlines to 2 (paragraph break)
            text = re.sub(r'\n{3,}', '\n\n', text)
        else:
            # Replace all newlines with spaces
            text = re.sub(r'\n+', ' ', text)
            text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    # Helper methods for number/date conversion
    
    def _number_to_words(self, n: int) -> str:
        """Convert number to words (simple implementation)."""
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
            if remainder:
                return hundreds + ' ' + self._number_to_words(remainder)
            return hundreds
        if n < 1000000:
            thousands = self._number_to_words(n // 1000) + ' thousand'
            remainder = n % 1000
            if remainder:
                return thousands + ' ' + self._number_to_words(remainder)
            return thousands
        
        # For larger numbers, return as digits (fallback)
        return str(n)
    
    def _number_to_ordinal(self, n: int) -> str:
        """Convert number to ordinal (first, second, third, etc.)."""
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
        
        # Fallback: construct ordinal
        words = self._number_to_words(n)
        if words.endswith('y'):
            return words[:-1] + 'ieth'
        elif words.endswith('one'):
            return words[:-3] + 'first'
        elif words.endswith('two'):
            return words[:-3] + 'second'
        elif words.endswith('three'):
            return words[:-5] + 'third'
        else:
            return words + 'th'
    
    def _get_currency_name(self, symbol: str) -> str:
        """Get currency name from symbol."""
        currency_map = {
            '£': 'pounds',
            '$': 'dollars',
            '€': 'euros',
        }
        return currency_map.get(symbol, 'currency units')
    
    def _get_month_name(self, month_abbr: str) -> str:
        """Convert month abbreviation to full name."""
        months = {
            'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
            'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
            'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
        }
        return months.get(month_abbr.lower()[:3], month_abbr)
    
    def _get_month_name_by_number(self, month_num: int) -> str:
        """Convert month number to full name."""
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        if 1 <= month_num <= 12:
            return months[month_num - 1]
        return str(month_num)
    
    def _format_year(self, year: str) -> str:
        """Format year as spoken (e.g., 2024 → twenty-twenty-four)."""
        year_int = int(year)
        
        if year_int < 2000:
            # Pre-2000: nineteen ninety-nine
            century = year_int // 100
            remainder = year_int % 100
            century_words = self._number_to_words(century)
            if remainder == 0:
                return f"{century_words} hundred"
            remainder_words = self._number_to_words(remainder)
            return f"{century_words} {remainder_words}"
        else:
            # Post-2000: twenty-twenty-four
            first_two = year_int // 100
            last_two = year_int % 100
            
            first_words = self._number_to_words(first_two)
            last_words = self._number_to_words(last_two)
            
            return f"{first_words}-{last_words}"


