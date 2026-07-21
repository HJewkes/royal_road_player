"""Pronunciation lexicon: respell hard words so XTTS pronounces them correctly.

XTTS v2 does its own grapheme-to-phoneme conversion, so the only lever on
pronunciation is the input spelling. This maps source words (recurring proper
nouns, place names, coined slang the STT defect scan flags as mangled) to
plain-letter respellings that render correctly, applied during normalization so
every future chapter benefits and used by the single-chunk regen verifier.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)

_RESERVED = {"_comment"}


class PronunciationLexicon:
    """Whole-word, case-insensitive respelling of hard-to-pronounce words."""

    def __init__(self, entries: dict[str, str]):
        self.entries = {k: v for k, v in entries.items() if k not in _RESERVED}
        self._pattern = self._compile(self.entries)

    @staticmethod
    def _compile(entries: dict[str, str]) -> Optional[re.Pattern]:
        keys = sorted((re.escape(k) for k in entries), key=len, reverse=True)
        if not keys:
            return None
        return re.compile(r"\b(" + "|".join(keys) + r")\b", re.IGNORECASE)

    def apply(self, text: str) -> str:
        """Replace every lexicon word with its respelling (idempotent)."""
        if self._pattern is None:
            return text
        lower = {k.lower(): v for k, v in self.entries.items()}
        return self._pattern.sub(lambda m: lower[m.group(0).lower()], text)

    @classmethod
    def load(cls, path: Path) -> "PronunciationLexicon":
        if not path.exists():
            logger.info(f"No pronunciation lexicon at {path}; using empty lexicon")
            return cls({})
        try:
            with open(path) as f:
                return cls(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load pronunciation lexicon {path}: {e}")
            return cls({})


# Grapheme rewrites that nudge XTTS toward a word's real pronunciation. Each is
# tried independently (and all-together) to build a small candidate set for the
# respelling sweep — English spelling irregularities XTTS routinely trips on.
_IC = re.IGNORECASE
_RESPELL_RULES = [
    (re.compile(r"^wr", _IC), "r"),        # Wrexham -> rexham
    (re.compile(r"^kn", _IC), "n"),        # knoll -> noll
    (re.compile(r"ph", _IC), "f"),         # -> f
    (re.compile(r"ough", _IC), "ow"),
    (re.compile(r"augh", _IC), "aw"),
    (re.compile(r"x", _IC), "ks"),         # Wrexham -> Wreksham
    (re.compile(r"y", _IC), "i"),          # Wythenshawe -> Withenshawe
    (re.compile(r"ch", _IC), "k"),
    (re.compile(r"e$", _IC), ""),          # drop silent trailing e
    (re.compile(r"ham$", _IC), "um"),      # British -ham place ending -> schwa
    (re.compile(r"shawe$", _IC), "shaw"),
    (re.compile(r"([bcdfghjklmnpqrstvwxz])\1", _IC), r"\1"),  # de-double consonants
]


def _match_case(variant: str, original: str) -> str:
    """Capitalize the variant if the original word was capitalized."""
    if original[:1].isupper() and variant:
        return variant[0].upper() + variant[1:]
    return variant


def generate_candidates(word: str, limit: int = 12) -> list[str]:
    """Heuristic respelling candidates for a hard word (excludes the original)."""
    out, seen = [], {word.lower()}
    cumulative = word
    for rule, repl in _RESPELL_RULES:
        for base in (word, cumulative):
            variant = _match_case(rule.sub(repl, base), word)
            if variant.lower() not in seen and variant:
                seen.add(variant.lower())
                out.append(variant)
        cumulative = rule.sub(repl, cumulative)  # accrete rules for a combined form
    return out[:limit]


_lexicon: Optional[PronunciationLexicon] = None


def get_lexicon() -> PronunciationLexicon:
    """Load the pronunciation lexicon singleton from the configured path."""
    global _lexicon
    if _lexicon is None:
        _lexicon = PronunciationLexicon.load(Path(get_settings().pronunciation_lexicon_path))
    return _lexicon
