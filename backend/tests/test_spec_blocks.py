"""Tests for placeholder-table (spec block) detection and decomposition.

The fixture is the real legend that opens DoF book 1 chapter 1, which reached
TTS verbatim and produced a minute of "Acceleration ex-ex, Flair ex-ex".
"""

import pytest

from src.text.spec_blocks import decompose_line, find_spec_blocks, is_spec_line

LEGEND = """CURSE ELEMENTS REFRESHER

Soccer Supremo Player Profiles

Born x.x.x (Age xx) Nationality

Acceleration xx Flair xx Set Pieces xx

Aggression xx Handling xx Stamina xx

Crossing xx Off The Ball xx

Decisions xx Pace xx preferred foot L

Determination xx Passing xx Form x-x-x-x-x

Dribbling xx Positioning xx Morale Good

Finishing xx Reflexes xx Condition 100%

CA xxx PA xxx

Gk DLRC M F

***

Selected Notes:

Attributes are rated out of 20, though it is possible to go beyond.
"""

PROSE = """Max walked to the touchline and considered his options.

The crowd was restless. Chester needed a goal, and they needed it now.

"Get forward," he shouted. "You have 20 minutes."
"""

ROSTER = """No. Name Pos Age Int Wage [CA PA] CA +/-

1. Marek Masarik GK 38 SVK 30000 [152 165] 11

13. Owen Elmham GK 37 18000 [157 164] 11
"""


@pytest.fixture
def block():
    blocks = find_spec_blocks(LEGEND)
    assert len(blocks) == 1
    return blocks[0]


def test_detects_the_legend_but_not_the_prose_around_it(block):
    assert block.lines[0] == "Born x.x.x (Age xx) Nationality"
    assert block.lines[-1] == "Gk DLRC M F"
    assert not any("Selected Notes" in ln for ln in block.lines)
    assert not any("Attributes are rated" in ln for ln in block.lines)


def test_code_row_after_a_blank_line_stays_in_the_block(block):
    """"Gk DLRC M F" is unreadable on its own and must not be left behind."""
    assert "Gk DLRC M F" in block.lines


def test_stops_at_the_authors_own_divider(block):
    assert not any(set(ln.strip()) == {"*"} for ln in block.lines)


def test_ordinary_prose_is_never_a_spec_block():
    assert find_spec_blocks(PROSE) == []


def test_roster_tables_are_left_to_the_stat_block_converter():
    """Rosters hold real data and rephrase into prose; legends hold none."""
    assert find_spec_blocks(ROSTER) == []


@pytest.mark.parametrize("line,expected", [
    ("Acceleration xx Flair xx Set Pieces xx",
     [("Acceleration", "xx"), ("Flair", "xx"), ("Set Pieces", "xx")]),
    ("Born x.x.x (Age xx) Nationality",
     [("Born", "x.x.x"), ("Age", "xx"), ("Nationality", None)]),
    ("Decisions xx Pace xx preferred foot L",
     [("Decisions", "xx"), ("Pace", "xx"), ("preferred foot", "L")]),
    ("Determination xx Passing xx Form x-x-x-x-x",
     [("Determination", "xx"), ("Passing", "xx"), ("Form", "x-x-x-x-x")]),
    ("Dribbling xx Positioning xx Morale Good",
     [("Dribbling", "xx"), ("Positioning", "xx"), ("Morale", "Good")]),
    ("Finishing xx Reflexes xx Condition 100%",
     [("Finishing", "xx"), ("Reflexes", "xx"), ("Condition", "100%")]),
])
def test_multi_word_labels_and_sample_values_decompose(line, expected):
    assert [(f.label, f.value) for f in decompose_line(line)] == expected


def test_a_lone_placeholder_line_is_not_a_block():
    """One stray line shouldn't trigger a rewrite; a legend is a run of them."""
    assert find_spec_blocks("He rated the kid xx out of 20.\n") == []


def test_sentence_punctuation_disqualifies_a_line():
    assert not is_spec_line("The rating was xx, which surprised him.")
    assert is_spec_line("Acceleration xx Flair xx")
