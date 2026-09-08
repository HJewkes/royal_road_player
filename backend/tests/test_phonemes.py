"""Tests for the phoneme-fidelity helpers (model-free; espeak-ng required)."""

import shutil

import pytest

from src.config import get_settings
from src.validation.phonemes import (
    chunk_word_verdicts, clean_ipa, detect_hallucinations, g2p, g2p_sentence,
    g2p_voice, phone_match_distance, phoneme_distance,
    XTTS_FAULT_THRESHOLD, XTTS_FAULT_THRESHOLD_SHORT,
)

espeak = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng not installed")


def test_clean_ipa_strips_stress_and_length_marks():
    assert clean_ipa("wˈɪθənʃˌɔː") == "wɪθənʃɔ"
    assert clean_ipa("  ɹˈɛksəm  ") == "ɹɛksəm"


def test_clean_ipa_folds_flap_and_open_schwa():
    """espeak writes the flap in "better" as ɾ where the recognizer hears t, and
    the two sides split schwa into ə/ɐ; neither difference is audible."""
    assert clean_ipa("bˈɛɾɐ") == clean_ipa("bˈɛtə")
    assert phoneme_distance("bɛɾɚ", "bɛtɚ") == 0.0


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


@espeak
def test_unusual_word_needs_a_bigger_gap_before_it_is_called_an_xtts_fault():
    """espeak anglicizes 'Bochum' to /bɒtʃəm/, so the German-correct /boʊkəm/ the
    audio says scores 0.5 against it. That distance is a real fault for a plain
    word but only G2P disagreement for a proper noun."""
    text = "the match in Bochum ended"
    parts = g2p_sentence(text)
    parts[3] = "boʊkəm"
    actual = "".join(parts)
    plain = chunk_word_verdicts(text, actual, targets=["Bochum"])[0]
    tagged = chunk_word_verdicts(text, actual, targets=["Bochum"], unusual={"Bochum"})[0]
    assert plain["distance"] == tagged["distance"]
    assert plain["source"] == "xtts"
    assert tagged["source"] == "whisper"


def test_g2p_voice_defaults_to_the_configured_accent(monkeypatch):
    monkeypatch.setattr(get_settings(), "phoneme_g2p_voice", "en-au")
    assert g2p_voice() == "en-au"
    assert g2p_voice("en-gb") == "en-gb"  # an explicit voice still wins


@espeak
def test_configured_accent_decides_whether_rhotic_audio_is_a_fault(monkeypatch):
    """The narrator and the phoneme recognizer are both rhotic. Predicting against
    a non-rhotic accent turns every r-coloured word into a false XTTS fault, which
    is what flooded the DoF book 8 ch 2 scan (over/here/career, 0.5-0.67 each)."""
    text = "his career was over"
    actual = "".join(g2p_sentence(text, voice="en-us"))
    monkeypatch.setattr(get_settings(), "phoneme_g2p_voice", "en-us")
    assert chunk_word_verdicts(text, actual, targets=["career"])[0]["source"] == "whisper"
    monkeypatch.setattr(get_settings(), "phoneme_g2p_voice", "en-gb")
    assert chunk_word_verdicts(text, actual, targets=["career"])[0]["source"] == "xtts"


@espeak
def test_short_word_needs_a_wider_gap_than_a_long_one():
    """A 3-phone word costs 0.33-0.5 for a single recognizer slip — ordinary-
    threshold territory — so the short band asks for a bigger break before blaming
    the audio. A whole-word swap still lands past it."""
    text = '"Dye Hard," I said.'
    swapped, near = g2p_sentence(text), g2p_sentence(text)
    swapped[0], near[0] = "ɡɹu", "zɔɪn"
    assert chunk_word_verdicts(text, "".join(swapped), targets=["Dye"])[0]["source"] == "xtts"
    assert chunk_word_verdicts(text, "".join(near), targets=["Dye"])[0]["source"] == "whisper"


@espeak
def test_long_word_keeps_the_ordinary_threshold():
    """The wider band is for short words only: a 6-phone word still counts as an
    XTTS fault at the ordinary 0.45, which is what keeps real mangles visible."""
    text = "the match in Salford ended"
    parts = g2p_sentence(text)
    parts[3] = "sɑlvɚt"
    verdict = chunk_word_verdicts(text, "".join(parts), targets=["Salford"])[0]
    assert XTTS_FAULT_THRESHOLD <= verdict["distance"] < XTTS_FAULT_THRESHOLD_SHORT
    assert verdict["source"] == "xtts"


def test_degenerate_span_from_duplicate_prefix_is_inconclusive_not_xtts():
    """Regression (DoF book 8 ch 2 chunk 437): "If I locked up Oka Okafor,
    Liverpool would..." — "Okafor" immediately follows the near-duplicate
    prefix "Oka". `_index_map`'s global alignment collapsed "Okafor"'s mapped
    span down to a single stray phone from the *start of "Liverpool"*, even
    though the audio (confirmed by ear) says "Okafor" just fine. That produced
    a false "xtts" verdict at severity 0.93 — the worst false positive in the
    chapter's scan. `actual` below is the real wav2vec2 phoneme recognition of
    that chunk's audio, hardcoded so this test needs no model load."""
    text = ("If I locked up Oka Okafor, Liverpool would effectively be playing "
            "with eight men. Eight and two halves, if we were being generous.")
    actual = ("ɪfaɪlɑktʌpoʊkɚʊkəfɔɹlɪvɚpulwʊdəfɛktɪvlibipleɪɪŋwɪðeɪtmɛneɪtændtu"
               "hævzɪfwiwɚbiŋdʒɛnɚɹəs")
    verdicts = {v["word"].lower(): v for v in
                chunk_word_verdicts(text, actual, targets=["Okafor"])}
    assert verdicts["okafor"]["source"] == "inconclusive"
    assert verdicts["okafor"]["source"] != "xtts"
