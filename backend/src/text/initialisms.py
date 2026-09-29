"""Spell out all-caps initialisms so XTTS reads them letter by letter.

XTTS reads an unfamiliar all-caps token as a word ("ASAP" -> "asaps", "FA" ->
"fa"). Dotted letters ("A. S. A. P.") make it say the letter names; bare spaced
letters do not, because a lone "A" is read as the article. But not every
all-caps token is an initialism: this corpus shouts ordinary words ("I did
NOT", "BEST") and names acronyms that are said as words (DOVE, UEFA, FIFA).
The rule therefore branches on token shape:

- Two letters: spell out, except a closed set of English two-letter words that
  only appear shouted (TO, IS, MY...), interjections (OI, UM, OK), am/pm and
  Roman numerals.
- Three to five letters with no vowel (Y counts as a vowel): spell out, since
  it cannot be read as a word (BBC, WSL, CFC), except interjections (HMM, HMPH).
- Three to five letters with a vowel: spell out only if listed in
  ``SPELLED_INITIALISMS``. In this corpus most such tokens are shouted words,
  so a general rule here would spell out "NOT" and "BEST".

A trailing lowercase plural "s" is kept on the last letter as "'s" ("CEOs" ->
"C. E. O's"), and tokens inside contractions ("I'LL", "DON'T") are left alone.
"""

import re

SHOUTED_TWO_LETTER_WORDS = frozenset({
    "AH", "AM", "AN", "AS", "AT", "AU", "AW", "BE", "BY", "DO", "EH", "GO",
    "HA", "HE", "HI", "IF", "IN", "IS", "IT", "ME", "MM", "MY", "NO", "OF",
    "OH", "OI", "OK", "ON", "OR", "OW", "PM", "SO", "TO", "UH", "UM", "UP",
    "US", "WE", "YA", "YO",
})

VOWELLESS_INTERJECTIONS = frozenset({
    "BRR", "GRR", "GRRR", "HMM", "HMMM", "HMPH", "MMM", "MMMM", "PFFT", "PSST",
    "SHH", "SHHH", "TSK", "ZZZ",
})

SPELLED_INITIALISMS = frozenset({
    "ACL", "AFC", "AKA", "AMC", "ASAP", "CEO", "CFO", "COO", "DNA", "EFL",
    "ESPN", "FBI", "IOU", "IMO", "IRL", "ITV", "MRI", "OMG", "PFA", "PGMOL",
    "POV", "QED", "ROI", "SEO", "SUV", "UFO", "USB", "USMNT", "VAR", "VIP",
    "WBA", "WFA",
})

_VOWELS = frozenset("AEIOUY")
_ROMAN_NUMERAL = re.compile(r"[IVX]+")
_CAPS_TOKEN = re.compile(r"(?<![\w'’])([A-Z]{2,5})(s?)\b(?!['’][A-Z])")
_SENTENCE_END = tuple(".!?…")


def is_initialism(token: str) -> bool:
    """Whether an all-caps token should be read letter by letter."""
    if _ROMAN_NUMERAL.fullmatch(token):
        return False
    if len(token) == 2:
        return token not in SHOUTED_TWO_LETTER_WORDS
    if not _VOWELS.intersection(token):
        return token not in VOWELLESS_INTERJECTIONS
    return token in SPELLED_INITIALISMS


def _spell(match: re.Match) -> str:
    token, plural = match.group(1), match.group(2)
    if not is_initialism(token):
        return match.group(0)
    letters = ". ".join(token)
    if plural:
        return letters + "'s"
    ends_sentence = match.string.startswith(_SENTENCE_END, match.end())
    return letters if ends_sentence else letters + "."


def spell_initialisms(text: str) -> str:
    """Replace every initialism in ``text`` with its dotted letters."""
    return _CAPS_TOKEN.sub(_spell, text)
