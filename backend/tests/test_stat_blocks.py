"""Tests for squad-roster stat-block rephrasing (StatBlockConverter).

The converter runs on RAW text before number normalization, so it must emit
DIGITS (152, 30000), keep the ability/potential stats and the CA-improvement
value, and be a strict no-op on anything that is not a roster block or a
league-record line.
"""

from src.text.stat_blocks import StatBlockConverter

STD_HEADER = "No. Name Pos Age Int Wage [CA PA] CA +/-"
LOAN_HEADER = "Name Pos Age Wage [CA PA] CA +/- Loan Club Loan Tier"


def convert(text: str) -> str:
    return StatBlockConverter().convert(text)


def row(line: str, loan: bool = False) -> str:
    """Convert a single roster row via its anchoring header.

    Rows are only rephrased inside a header-anchored block (so the converter
    never mistakes prose for a table); wrapping one row under a bare header
    isolates the row parser while still exercising that path.
    """
    header = LOAN_HEADER if loan else STD_HEADER
    return convert(f"{header}\n{line}")


# --- Roster rows: the four canonical examples from the spec ------------------

def test_standard_row_with_nationality_and_change():
    out = row("1. Marek Masarik GK 38 SVK 30000 [152 165] 11")
    assert out == (
        "Number 1, Marek Masarik, goalkeeper, age 38, Slovakia, wage £30000. "
        "PA 165, CA 152, up 11."
    )


def test_multi_role_and_negative_potential():
    """A negative PA sentinel is kept literal (minus N), not hidden as 'unknown'."""
    out = row("12. Magnus Evergreen D,DM,M 31 SCO 18000 [150 -2] 16")
    assert out == (
        "Number 12, Magnus Evergreen, defender, defensive midfielder, "
        "midfielder, age 31, Scotland, wage £18000. "
        "PA minus 2, CA 150, up 16."
    )


def test_row_without_ability_bracket():
    out = row("77. Max Best Omni 28   50000")
    assert out == "Number 77, Max Best, utility player, age 28, wage £50000."


def test_loan_row_with_club_and_tier():
    out = row("Nasa DR 23 4000 [126 150] 12 College CL", loan=True)
    assert out == (
        "Nasa, defender right, age 23, wage £4000. "
        "PA 150, CA 126, up 12. On loan at College, loan tier CL."
    )


# --- Roster edge cases -------------------------------------------------------

def test_womens_row_footnote_name_and_youth_marker():
    """A '*' footnote marker is stripped from the name; a u19 youth marker is
    consumed silently and never voiced."""
    out = row("20. Tanwen DC 19 WAL u19 500 [91 106] 9")
    assert "*" not in out
    assert "u19" not in out
    assert out == (
        "Number 20, Tanwen, defender centre, age 19, Wales, wage £500. "
        "PA 106, CA 91, up 9."
    )


def test_name_asterisk_and_missing_wage_and_change():
    out = row("Miina Timonen* GK 18     [36 184]")
    assert out == (
        "Miina Timonen, goalkeeper, age 18. PA 184, CA 36."
    )


def test_no_leading_number_prefix_is_omitted():
    out = row("Ruud Berkenbosch S 21   48000 [138 188] 5")
    assert out.startswith("Ruud Berkenbosch,")
    assert "Number" not in out


def test_multiword_loan_club():
    out = row("Aston Davidson GK 19 600 [60 113] 8 Connah's Quay 6", loan=True)
    assert out.endswith("On loan at Connah's Quay, loan tier 6.")


def test_negative_potential_kept_literal_and_positive_change_up():
    out = row("Dan Badford MC 20 4000 [135 -1] 14 Saltney CL", loan=True)
    assert "PA minus 1" in out
    assert "up 14" in out
    assert out.endswith("On loan at Saltney, loan tier CL.")


def test_side_letters_before_role_code():
    """'RM' means right midfielder (side before role stem)."""
    out = row("15. Bark RM 22 JAM 9000 [130 130] 3")
    assert "Bark, midfielder right, age 22, Jamaica" in out


def test_forward_with_trailing_sides():
    out = row("26. Pascal Bochum F RLC 23   10000 [140 140] 2")
    assert "forward left, right and centre" in out
    assert "up 2" in out


def test_zero_change_renders_as_no_change():
    out = row("25. Sticky GK 34   4000 [122 122] 0")
    assert out.endswith("PA 122, CA 122, no change.")


def test_unknown_nationality_is_omitted():
    out = row("5. Foo Bar D 24 XYZ 1000 [100 120] 5")
    assert "XYZ" not in out
    assert out == (
        "Number 5, Foo Bar, defender, age 24, wage £1000. "
        "PA 120, CA 100, up 5."
    )


# --- Header detection & block consumption ------------------------------------

def test_header_dropped_and_block_stops_at_prose():
    text = (
        "No. Name Pos Age Int Wage [CA PA] CA +/-\n"
        "\n"
        "1. Marek Masarik GK 38 SVK 30000 [152 165] 11\n"
        "25. Sticky GK 34   4000 [122 122] 0\n"
        "\n"
        "Sticky (3K), Peter (2K), and Magnus (1K) are paid separately.\n"
    )
    out = convert(text)
    # The raw column-label header is gone.
    assert "No. Name Pos" not in out
    assert "[CA PA]" not in out
    # Both rows converted.
    assert "Number 1, Marek Masarik, goalkeeper" in out
    assert "Number 25, Sticky, goalkeeper" in out
    # Trailing prose survives unchanged and is not swallowed into the block.
    assert "Sticky (3K), Peter (2K), and Magnus (1K) are paid separately." in out


def test_loan_header_detected_and_block_converted():
    text = (
        "Name Pos Age Wage [CA PA] CA +/- Loan Club Loan Tier\n"
        "\n"
        "Nasa DR 23 4000 [126 150] 12 College CL\n"
        "\n"
        "Women's Team: 2nd in WSL (Tier 1, 14 teams)\n"
    )
    out = convert(text)
    assert "Loan Tier" not in out
    assert "On loan at College, loan tier CL." in out
    assert "Women's Team: 2nd in WSL (Tier 1, 14 teams)" in out


# --- Record lines ------------------------------------------------------------

def test_record_line_mens_variant_with_minus_and_footnote():
    line = ("P19 - W4 - D5 - L10 - Goals For 23 - Goals Against 35 - "
            "Goal Difference minus 12 - Points 14*")
    out = convert(line)
    assert out == (
        "Played 19, won 4, drawn 5, lost 10. "
        "Goals for 23, goals against 35, goal difference minus 12, 14 points."
    )


def test_record_line_womens_variant():
    line = ("P11 - W7 - D3 - L1 - Goals For 20 - Goals Against 10 - "
            "Goal Difference 10 - Points 24")
    out = convert(line)
    assert out == (
        "Played 11, won 7, drawn 3, lost 1. "
        "Goals for 20, goals against 10, goal difference 10, 24 points."
    )


# --- No-op guarantee ---------------------------------------------------------

def test_ordinary_prose_passes_through_byte_identical():
    prose = (
        "Max owns four Savile Row suits, a Bayern Munich scarf, a fast laptop,\n"
        "two framed photos featuring members of the Yalley family, a wedding\n"
        "ring, and a bottle of Ribena with sentimental value.\n"
        "\n"
        "XP balance: 4,819\n"
        "Manager Ranking*: 18 (+1)\n"
        "AOK Cup - knocked out\n"
    )
    assert convert(prose) == prose


def test_non_roster_bracket_line_is_not_treated_as_a_row():
    line = "[Premier League average CA range this season: 146 to 171]"
    assert convert(line) == line
