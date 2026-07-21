"""Tests for the phoneme-fidelity helpers (model-free; espeak-ng required)."""

import shutil

import pytest

from src.validation.phonemes import (
    chunk_word_verdicts, clean_ipa, detect_hallucinations, g2p, g2p_sentence,
    phone_match_distance, phoneme_distance,
)

espeak = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng not installed")


def test_clean_ipa_strips_stress_and_length_marks():
    assert clean_ipa("wˈɪθənʃˌɔː") == "wɪθənʃɔ"
    assert clean_ipa("  ɹˈɛksəm  ") == "ɹɛksəm"


def test_phoneme_distance_identical_is_zero():
    assert phoneme_distance("wɪθənʃɔ", "wɪθənʃɔ") == 0.0


def test_phoneme_distance_orders_similar_before_different():
    near = phoneme_distance("wɪθənʃɔ", "wɪðɪnʃɔ")
    far = phoneme_distance("wɪθənʃɔ", "bɒʃtaɪstɪk")
    assert near < far
    assert far > 0.5


@espeak
def test_g2p_produces_phonemes_for_proper_noun_and_coinage():
    assert g2p("Wrexham")  # non-empty
    assert g2p("boshtastic")  # coined word still gets phonemes via rules


@espeak
def test_g2p_distinguishes_distinct_words():
    assert phoneme_distance(g2p("Wythenshawe"), g2p("boshtastic")) > 0.5


def test_phone_match_finds_word_inside_full_chunk_phones():
    # "wɪθənʃɔ" embedded in a longer phone string of neighbouring words
    full = "haʊsɪnwɪθənʃɔəɡɛn"
    assert phone_match_distance("wɪθənʃɔ", full) < 0.15


def test_phone_match_high_when_word_absent():
    assert phone_match_distance("wɪθənʃɔ", "bɒʃtaɪstɪkwɛmə") > 0.5


def test_phone_match_empty_expected_is_zero():
    assert phone_match_distance("", "anything") == 0.0


@espeak
def test_positional_verdict_flags_garbled_word_not_neighbours():
    """A word garbled at its position must score high even if its phones happen
    to appear elsewhere in the chunk (the fuzzy-match failure mode)."""
    text = "the match in Bochum ended"
    # actual audio: every word correct EXCEPT 'Bochum', replaced by garbage phones
    parts = g2p_sentence(text)  # per-word phones, cleaned
    parts[3] = "zzzzxq"  # garble the Bochum slot
    actual = "".join(parts)
    verdicts = {v["word"].lower(): v for v in
                chunk_word_verdicts(text, actual, targets=["Bochum", "match"])}
    assert verdicts["bochum"]["source"] == "xtts"
    assert verdicts["match"]["source"] == "whisper"  # untouched word stays low


@espeak
def test_verdict_without_targets_returns_empty():
    assert chunk_word_verdicts("hello world", "hɛloʊwɜld") == []


@espeak
def test_detect_hallucination_flags_inserted_babble():
    """A run of audio phones with no source text is a hallucinated outburst."""
    text = "absolutely perfect Heli eyed me"
    parts = g2p_sentence(text)
    # inject babble phones between 'perfect' and 'Heli'
    parts.insert(2, "wʌnʃɹi")
    actual = "".join(parts)
    halluc = detect_hallucinations(text, actual)
    assert halluc and any("wʌnʃɹi" in h["phones"] for h in halluc)
    assert halluc[0]["length"] >= 5


@espeak
def test_clean_audio_has_no_hallucination():
    text = "absolutely perfect Heli eyed me"
    actual = "".join(g2p_sentence(text))
    assert detect_hallucinations(text, actual) == []


@espeak
def test_short_word_not_called_xtts_fault_despite_high_distance():
    """A 1-2 phone word must not be a trustworthy XTTS-fault (coarse metric)."""
    text = "I am here"  # 'I' and 'am' are very short
    parts = g2p_sentence(text)
    parts[0] = "z"  # garble the 1-phone word 'I'
    actual = "".join(parts)
    verdicts = {v["word"].lower(): v for v in
                chunk_word_verdicts(text, actual, targets=["I"])}
    assert verdicts["i"]["source"] == "whisper"  # too short to trust as xtts-fault
