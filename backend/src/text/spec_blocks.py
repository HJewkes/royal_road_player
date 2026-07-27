"""Detect and decompose specification blocks — tables whose values are placeholders.

The author opens each book with a legend for the in-world game interface: a
player profile laid out in columns where every value is a placeholder ("xx"
means "a rating goes here"). Read aloud it becomes a minute of "Acceleration
ex-ex, Flair ex-ex".

This is a different problem from the appendix rosters that ``StatBlockConverter``
handles. A roster holds real data, so rephrasing it as prose preserves the
information. A legend holds no data at all, so there is no faithful reading —
the only question is what to say instead. Detection is therefore kept separate
from rendering: ``find_spec_blocks`` locates and decomposes, and the caller
decides whether to skip, summarise, or voice the field names.

Detection is structural rather than layout-specific: a run of short, unpunctuated
lines carrying placeholder values. It does not know about football, so it also
catches the next legend the author invents in a different shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "xx", "xxx", "x.x.x", "x-x-x-x-x" — a value the author left blank on purpose.
_PLACEHOLDER = re.compile(r"^x{1,4}(?:[.\-]x{1,4})*$", re.IGNORECASE)
# Concrete sample values used to illustrate the legend ("Condition 100%").
_SAMPLE_VALUE = re.compile(r"^(?:\d{1,3}%?|[LRC])$")
_SAMPLE_WORDS = {"good", "poor", "fair", "average", "excellent", "superb"}
# Sentence punctuation means prose, not a table row.
_PROSE_ENDING = re.compile(r"[.!?:;,]$")

MIN_BLOCK_LINES = 3


@dataclass
class Field:
    """One label/value pair from a spec line. value is None for a bare label."""

    label: str
    value: str | None

    @property
    def is_placeholder(self) -> bool:
        return bool(self.value and _PLACEHOLDER.match(self.value))


@dataclass
class SpecBlock:
    """A contiguous run of spec lines, with its position in the source lines."""

    start: int
    end: int  # exclusive
    lines: list[str] = field(default_factory=list)
    rows: list[list[Field]] = field(default_factory=list)

    @property
    def fields(self) -> list[Field]:
        return [f for row in self.rows for f in row]

    @property
    def placeholder_count(self) -> int:
        return sum(1 for f in self.fields if f.is_placeholder)

    @property
    def labels(self) -> list[str]:
        return [f.label for f in self.fields if f.label]


def _is_value(token: str) -> bool:
    """Is this token a value rather than part of a label?"""
    return bool(
        _PLACEHOLDER.match(token)
        or _SAMPLE_VALUE.match(token)
        or token.lower() in _SAMPLE_WORDS
    )


def decompose_line(line: str) -> list[Field]:
    """Split a spec line into its label/value pairs.

    Labels run until a value token, so "Acceleration xx Flair xx" yields two
    fields and multi-word labels like "Set Pieces xx" survive intact. A trailing
    label with no value (a column header such as "Nationality") is kept with
    value None rather than dropped, so nothing silently disappears.
    """
    fields: list[Field] = []
    label_words: list[str] = []
    for token in line.replace("(", " ").replace(")", " ").split():
        if _is_value(token) and label_words:
            fields.append(Field(" ".join(label_words), token))
            label_words = []
        else:
            label_words.append(token)
    if label_words:
        fields.append(Field(" ".join(label_words), None))
    return fields


def is_spec_line(line: str) -> bool:
    """A short, unpunctuated line carrying at least one placeholder value."""
    stripped = line.strip()
    if not stripped or _PROSE_ENDING.search(stripped) or len(stripped) > 90:
        return False
    return any(_PLACEHOLDER.match(tok) for tok in stripped.split())


def _is_separator(line: str) -> bool:
    """A divider such as "***" — the author's own block boundary."""
    stripped = line.strip()
    return bool(stripped) and not any(c.isalnum() for c in stripped)


def _is_block_filler(line: str) -> bool:
    """A short unpunctuated line with no placeholder — kept only when it sits
    between spec lines, so a legend's header and code row ("Gk DLRC M F") stay
    with the block instead of being read out on their own."""
    stripped = line.strip()
    if not stripped or _is_separator(line) or len(stripped) > 90:
        return False
    return not _PROSE_ENDING.search(stripped)


def find_spec_blocks(text: str) -> list[SpecBlock]:
    """Locate every placeholder-table region in ``text``.

    Returns blocks in source order; empty when the text is ordinary prose.
    """
    lines = text.split("\n")
    blocks: list[SpecBlock] = []
    i = 0
    while i < len(lines):
        if not is_spec_line(lines[i]):
            i += 1
            continue
        start, end, last_spec = i, i, i
        while end < len(lines) and (
            is_spec_line(lines[end]) or not lines[end].strip() or _is_block_filler(lines[end])
        ):
            if is_spec_line(lines[end]):
                last_spec = end
            end += 1
        end = _extend_to_trailing_filler(lines, last_spec, end)
        block = _build_block(lines, start, end)
        if len(block.rows) >= MIN_BLOCK_LINES:
            blocks.append(block)
        i = max(end, i + 1)
    return blocks


def _extend_to_trailing_filler(lines: list[str], last_spec: int, end: int) -> int:
    """Keep filler that follows the last placeholder line — the legend's code
    row ("Gk DLRC M F"), which is separated from it by a blank line — but stop
    at the author's own divider so the prose after the block is left alone."""
    stop = last_spec + 1
    while stop < end:
        if not lines[stop].strip():  # blank lines separate the legend's rows
            stop += 1
            continue
        if not _is_block_filler(lines[stop]):
            break
        stop += 1
    while stop > last_spec + 1 and not lines[stop - 1].strip():
        stop -= 1  # don't trail blank lines into the block
    return stop


def _build_block(lines: list[str], start: int, end: int) -> SpecBlock:
    content = [ln for ln in lines[start:end] if ln.strip()]
    return SpecBlock(
        start=start,
        end=end,
        lines=content,
        rows=[decompose_line(ln) for ln in content],
    )
