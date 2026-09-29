"""Tests for spelling out all-caps initialisms before TTS."""

import pytest
from src.text.initialisms import spell_initialisms
from src.text.normalizer import TextNormalizer


def test_asap_is_spelled_out():
    text = "We need to get him here ASAP."
    assert spell_initialisms(text) == "We need to get him here A. S. A. P."


def test_fa_is_spelled_out():
    text = "the FA has thought about it"
    assert spell_initialisms(text) == "the F. A. has thought about it"


def test_ca_is_spelled_out_like_other_stat_abbreviations():
    assert spell_initialisms("His CA was 'only' 120") == "His C. A. was 'only' 120"


def test_word_read_acronym_is_left_alone():
    text = "DOVE rates them, and UEFA agrees."
    assert spell_initialisms(text) == text


def test_shouted_words_are_left_alone():
    text = "I did NOT say that. TO THE BEST OF MY knowledge, IT IS fine."
    assert spell_initialisms(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # two letters: spelled out unless a shouted English word
        ("the FA Cup", "the F. A. Cup"),
        ("watch TV", "watch T. V."),
        ("GO now", "GO now"),
        ("at 10 PM", "at 10 PM"),
        ("Henry VI", "Henry VI"),
        # three to five letters without a vowel: always spelled out
        ("the WSL title", "the W. S. L. title"),
        ("on the BBC", "on the B. B. C."),
        ("HMM, maybe", "HMM, maybe"),
        # three to five letters with a vowel: only if allowlisted
        ("the new CEO", "the new C. E. O."),
        ("the MAX update", "the MAX update"),
        # a sentence-ending period is not doubled
        ("Is it ASAP?", "Is it A. S. A. P?"),
        # plurals and possessives keep the suffix on the last letter
        ("two CEOs", "two C. E. O's"),
        ("the FA's decision", "the F. A.'s decision"),
        # contractions in shouted text are not initialisms
        ("I'LL WAIT", "I'LL WAIT"),
        ("WE'VE WON", "WE'VE WON"),
        # mixed case and longer tokens are not initialisms
        ("Fa and Tv", "Fa and Tv"),
        ("GOOOAL", "GOOOAL"),
    ],
)
def test_rule_branches(text, expected):
    assert spell_initialisms(text) == expected


@pytest.mark.parametrize(
    "interjection", ["OI", "UH", "UM", "AW", "MM", "OK", "HMPH", "GRRR"]
)
def test_interjections_stay_words(interjection):
    text = f"{interjection}, you there!"
    assert spell_initialisms(text) == text


def test_normalizer_spells_initialisms_end_to_end():
    out = TextNormalizer().normalize("The FA wants it ASAP, said the CEO.")
    assert out == "The F. A. wants it A. S. A. P., said the C. E. O."
