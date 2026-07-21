"""Tests for STT-based TTS defect detection."""

from src.validation.defects import (
    confirm_defects,
    detect_defects,
    phonetic_distance,
    tokenize,
    _numeric_value,
    _scan_number,
)


def _rich(pairs, segments=None):
    """Build a rich STT result from (word, probability) pairs with fake timing."""
    words = [
        {"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "probability": p}
        for i, (w, p) in enumerate(pairs)
    ]
    return {
        "text": " ".join(w for w, _ in pairs),
        "segments": segments or [],
        "words": words,
    }


def test_phonetic_homophones_are_zero_distance():
    assert phonetic_distance("their", "there") == 0.0
    assert phonetic_distance("dear", "deer") == 0.0
    assert phonetic_distance("aegis", "eejis") > 0.0


def test_numeric_value_maps_digits_and_words():
    assert _numeric_value("50") == 50
    assert _numeric_value("fifty") == 50
    assert _numeric_value("word") is None


def test_confident_homophone_is_not_flagged():
    expected = "they left their house"
    rich = _rich([("they", 0.99), ("left", 0.98), ("there", 0.97), ("house", 0.98)])
    assert detect_defects(expected, rich) == []


def test_digit_spoken_as_word_is_not_a_defect():
    expected = "chapter 50 begins"
    rich = _rich([("chapter", 0.98), ("fifty", 0.95), ("begins", 0.97)])
    assert [d for d in detect_defects(expected, rich) if d.kind == "substitution"] == []


def test_real_number_mangle_is_flagged():
    expected = "chapter 50 begins"
    rich = _rich([("chapter", 0.98), ("fifteen", 0.6), ("begins", 0.97)])
    subs = [d for d in detect_defects(expected, rich) if d.kind == "substitution"]
    assert subs and subs[0].expected == "50" and "number" in subs[0].causes


def test_mangled_word_surfaces_with_low_confidence_boost():
    expected = "the aegis protected them"
    rich = _rich([("the", 0.99), ("eejis", 0.3), ("protected", 0.96), ("them", 0.95)])
    subs = [d for d in detect_defects(expected, rich) if d.expected == "aegis"]
    assert subs and subs[0].severity > 0.3


def test_count_mismatch_groups_into_single_defect():
    """A run garbled into a different word count is one event, not many rows."""
    expected = "Deaaaaaaaarrrrrr Dani spoke"
    rich = _rich([("Dia", 0.5), ("R", 0.4), ("Dhani", 0.5), ("spoke", 0.95)])
    subs = [d for d in detect_defects(expected, rich) if d.kind == "substitution"]
    assert len(subs) == 1
    assert "stylized_elongation" in subs[0].causes


def test_low_confidence_segment_is_flagged_even_when_words_align():
    expected = "the empire stood firm"
    rich = _rich(
        [("the", 0.9), ("empire", 0.9), ("stood", 0.9), ("firm", 0.9)],
        segments=[{
            "start": 0.0, "end": 2.0, "text": "the empire stood firm",
            "avg_logprob": -1.6, "compression_ratio": 1.4, "no_speech_prob": 0.01,
        }],
    )
    kinds = {d.kind for d in detect_defects(expected, rich)}
    assert "low_confidence" in kinds


def test_defects_sorted_by_severity_descending():
    expected = "the aegis of the foobarbaz empire"
    rich = _rich([
        ("the", 0.99), ("eejis", 0.3), ("of", 0.98), ("the", 0.98),
        ("zorptrix", 0.2), ("empire", 0.97),
    ])
    defects = detect_defects(expected, rich)
    sevs = [d.severity for d in defects]
    assert sevs == sorted(sevs, reverse=True)


def test_tokenize_collapses_elongation_but_keeps_original():
    toks = tokenize("Deaaaaaaaarrrrrr")
    assert toks[0].norm == "dear"
    assert toks[0].original == "Deaaaaaaaarrrrrr"


def test_scan_number_parses_multiword_cardinals():
    assert _scan_number(["two", "hundred", "fifty"], 0) == (250, 3)
    assert _scan_number(["one", "hundred", "forty", "nine"], 0) == (149, 4)
    assert _scan_number(["thirty", "three"], 0) == (33, 2)
    assert _scan_number(["50"], 0) == (50, 1)
    # grammar-aware split: "one thirty six" is [1, 36], not 37
    assert _scan_number(["one", "thirty", "six"], 0) == (1, 1)
    assert _scan_number(["seven", "thousand", "two", "hundred", "fifty"], 0) == (7250, 5)
    assert _scan_number(["house"], 0) == (None, 0)


def test_multiword_number_not_flagged_when_spoken_correctly():
    """Source '250' heard as 'two hundred fifty' (or vice-versa) is not a defect."""
    expected = "he owed 250 gold"
    rich = _rich([("he", 0.99), ("owed", 0.98),
                  ("two", 0.9), ("hundred", 0.9), ("fifty", 0.9), ("gold", 0.97)])
    subs = [d for d in detect_defects(expected, rich) if d.kind == "substitution"]
    assert subs == []


def test_letter_read_as_its_name_is_not_flagged():
    expected = "grade C was fine"
    rich = _rich([("grade", 0.98), ("see", 0.9), ("was", 0.97), ("fine", 0.97)])
    assert [d for d in detect_defects(expected, rich) if d.expected == "C"] == []


def test_confirm_keeps_defect_both_models_agree_on():
    expected = "the aegis protected them"
    base = _rich([("the", 0.99), ("eejis", 0.3), ("protected", 0.96), ("them", 0.95)])
    strong = _rich([("the", 0.99), ("eejit", 0.6), ("protected", 0.98), ("them", 0.98)])
    base_defects = detect_defects(expected, base)
    kept = confirm_defects(base_defects, expected, strong)
    assert any(d.expected == "aegis" for d in kept)


def test_confirm_drops_base_only_false_positive():
    """If the stronger model agrees with the source, the base flag is dropped."""
    expected = "she left the house"
    base = _rich([("he", 0.4), ("left", 0.9), ("the", 0.9), ("house", 0.9)])
    strong = _rich([("she", 0.95), ("left", 0.98), ("the", 0.98), ("house", 0.98)])
    base_defects = detect_defects(expected, base)
    assert any(d.expected == "she" for d in base_defects)  # base flagged it
    assert confirm_defects(base_defects, expected, strong) == []  # confirm clears it


def test_confirm_returns_empty_when_no_base_defects():
    strong = _rich([("clean", 0.99), ("audio", 0.99)])
    assert confirm_defects([], "clean audio", strong) == []
