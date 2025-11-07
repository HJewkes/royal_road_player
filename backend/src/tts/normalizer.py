"""Text normalization for TTS generation."""

import re
from typing import Optional


def normalize_punctuation(text: str) -> str:
    """
    Normalize punctuation for better TTS pronunciation.
    
    - Convert straight quotes to curly quotes
    - Convert -- to em-dash —
    - Collapse repeated punctuation
    - Convert ... to ellipsis …
    
    Args:
        text: Raw text
        
    Returns:
        Text with normalized punctuation
    """
    # Convert straight quotes to curly quotes
    # Handle opening quotes (after whitespace or start)
    text = re.sub(r'(^|\s)"([^"]+)"', r'\1"\2"', text)
    # Handle closing quotes
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


def normalize_acronyms(text: str, acronym_map: dict[str, str]) -> str:
    """
    Expand acronyms according to rule map.
    
    Args:
        text: Text to process
        acronym_map: Dictionary mapping acronyms to expanded forms
        
    Returns:
        Text with expanded acronyms
    """
    # Sort by length (longest first) to avoid partial matches
    sorted_acronyms = sorted(acronym_map.items(), key=lambda x: len(x[0]), reverse=True)
    
    for acronym, expansion in sorted_acronyms:
        # Word boundary check - only match whole words
        pattern = r'\b' + re.escape(acronym) + r'\b'
        text = re.sub(pattern, expansion, text)
    
    return text


def normalize_numbers(text: str, number_style: str = "words") -> str:
    """
    Normalize numbers to spoken form.
    
    Handles:
    - Ages: 28-year-old → twenty-eight-year-old
    - Currency: £800,000 → eight hundred thousand pounds
    - Simple numbers: 14 → fourteen
    
    Args:
        text: Text to process
        number_style: "words" or "digits" (for currency)
        
    Returns:
        Text with normalized numbers
    """
    # Age normalization: X-year-old → X-year-old (spoken)
    def age_replacer(match):
        num = match.group(1)
        try:
            num_int = int(num)
            words = number_to_words(num_int)
            return f"{words}-year-old"
        except (ValueError, AttributeError):
            return match.group(0)
    
    text = re.sub(r'(\d+)-year-old', age_replacer, text)
    
    # Currency normalization
    if number_style == "words":
        # £800,000 → eight hundred thousand pounds
        def currency_replacer(match):
            symbol = match.group(1)  # £, $, etc.
            amount = match.group(2).replace(',', '')
            try:
                amount_int = int(amount)
                words = number_to_words(amount_int)
                currency_name = get_currency_name(symbol)
                return f"{words} {currency_name}"
            except (ValueError, AttributeError):
                return match.group(0)
        
        text = re.sub(r'([£$€])([\d,]+)', currency_replacer, text)
    
    return text


def normalize_dates(text: str, date_style: str = "spoken") -> str:
    """
    Normalize dates to spoken form.
    
    Patterns:
    - 4 Feb, 2024 → the fourth of February, twenty-twenty-four
    - 04/02/2024 → the fourth of February, twenty-twenty-four
    
    Args:
        text: Text to process
        date_style: "spoken" or "numeric"
        
    Returns:
        Text with normalized dates
    """
    if date_style != "spoken":
        return text
    
    # Pattern: Day Month, Year (e.g., "4 Feb, 2024")
    def date_replacer1(match):
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        
        try:
            day_int = int(day)
            day_ordinal = number_to_ordinal(day_int)
            month_name = get_month_name(month)
            year_spoken = format_year(year)
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
            day_ordinal = number_to_ordinal(day_int)
            month_name = get_month_name_by_number(month_int)
            year_spoken = format_year(year)
            return f"{day_ordinal} of {month_name}, {year_spoken}"
        except (ValueError, AttributeError):
            return match.group(0)
    
    text = re.sub(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_replacer2, text)
    
    return text


def normalize_whitespace(text: str, preserve_paragraphs: bool = True) -> str:
    """
    Normalize whitespace while preserving structure.
    
    - Collapse excess spaces
    - Preserve paragraph breaks (double newlines)
    - Normalize tabs to spaces
    
    Args:
        text: Text to process
        preserve_paragraphs: If True, preserve paragraph breaks
        
    Returns:
        Text with normalized whitespace
    """
    # Normalize tabs to spaces
    text = text.replace('\t', ' ')
    
    # Collapse multiple spaces to single space (within lines)
    text = re.sub(r' +', ' ', text)
    
    if preserve_paragraphs:
        # Normalize 3+ newlines to 2 (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Preserve double newlines as paragraph breaks
    else:
        # Replace all newlines with spaces
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r' +', ' ', text)
    
    return text.strip()


def normalize(raw_text: str, rules: Optional[dict] = None) -> list[str]:
    """
    Normalize raw text for TTS generation.
    
    Applies all normalization steps and returns list of paragraphs.
    
    Args:
        raw_text: Raw input text
        rules: Optional normalization rules dict with keys:
            - acronym_map: dict[str, str]
            - number_style: "words" | "digits"
            - date_style: "spoken" | "numeric"
            - preserve_paragraphs: bool
            
    Returns:
        List of normalized paragraphs
    """
    if rules is None:
        rules = {}
    
    text = raw_text
    
    # Apply normalization steps in order
    text = normalize_punctuation(text)
    
    # Acronym expansion
    if 'acronym_map' in rules:
        text = normalize_acronyms(text, rules['acronym_map'])
    
    # Number normalization
    number_style = rules.get('number_style', 'words')
    text = normalize_numbers(text, number_style)
    
    # Date normalization
    date_style = rules.get('date_style', 'spoken')
    text = normalize_dates(text, date_style)
    
    # Whitespace normalization
    preserve_paragraphs = rules.get('preserve_paragraphs', True)
    text = normalize_whitespace(text, preserve_paragraphs)
    
    # Split into paragraphs
    if preserve_paragraphs:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    else:
        paragraphs = [text] if text.strip() else []
    
    return paragraphs


# Helper functions for number/date conversion

def number_to_words(n: int) -> str:
    """
    Convert number to words (simple implementation).
    
    For production, consider using 'inflect' library.
    """
    # Basic implementation for common numbers
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
            return hundreds + ' ' + number_to_words(remainder)
        return hundreds
    if n < 1000000:
        thousands = number_to_words(n // 1000) + ' thousand'
        remainder = n % 1000
        if remainder:
            return thousands + ' ' + number_to_words(remainder)
        return thousands
    
    # For larger numbers, return as digits (fallback)
    return str(n)


def number_to_ordinal(n: int) -> str:
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
    words = number_to_words(n)
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


def get_currency_name(symbol: str) -> str:
    """Get currency name from symbol."""
    currency_map = {
        '£': 'pounds',
        '$': 'dollars',
        '€': 'euros',
    }
    return currency_map.get(symbol, 'currency units')


def get_month_name(month_abbr: str) -> str:
    """Convert month abbreviation to full name."""
    months = {
        'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
        'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
        'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
    }
    return months.get(month_abbr.lower()[:3], month_abbr)


def get_month_name_by_number(month_num: int) -> str:
    """Convert month number to full name."""
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    if 1 <= month_num <= 12:
        return months[month_num - 1]
    return str(month_num)


def format_year(year: str) -> str:
    """Format year as spoken (e.g., 2024 → twenty-twenty-four)."""
    year_int = int(year)
    
    if year_int < 2000:
        # Pre-2000: nineteen ninety-nine
        century = year_int // 100
        remainder = year_int % 100
        century_words = number_to_words(century)
        if remainder == 0:
            return f"{century_words} hundred"
        remainder_words = number_to_words(remainder)
        return f"{century_words} {remainder_words}"
    else:
        # Post-2000: twenty-twenty-four
        first_two = year_int // 100
        last_two = year_int % 100
        
        first_words = number_to_words(first_two)
        last_words = number_to_words(last_two)
        
        return f"{first_words}-{last_words}"

