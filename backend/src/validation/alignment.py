"""Shared sequence alignment for validation, with difflib's autojunk heuristic off."""

from collections.abc import Sequence
from difflib import SequenceMatcher


def exact_matcher(a: Sequence, b: Sequence) -> SequenceMatcher:
    """A SequenceMatcher with autojunk off.

    From 200 elements up, autojunk discards every element that makes up over 1% of
    the second sequence as junk. Small alphabets (characters, phones) then collapse
    the alignment: a faithful 250-character chunk scores far below its true
    similarity, and a long run of words can come back as one big insertion.
    """
    return SequenceMatcher(None, a, b, autojunk=False)
