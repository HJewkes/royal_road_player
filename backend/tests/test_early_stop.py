"""The early-stop guard: a take that reads its text impossibly fast was cut short."""

import wave

import pytest

from src.tts.early_stop import early_stop_shortfall, spoken_letters, wav_duration
from src.tts.profiles import P4

# 30 alphanumeric letters per sentence, written for this test.
SENTENCE = "The green boat drifted far out to sea. "


def _text_with_letters(letters: int) -> str:
    text = SENTENCE * (letters // 30)
    assert spoken_letters(text) == letters
    return text


def _shortfall(text: str, audio_s: float):
    return early_stop_shortfall(text, audio_s, P4.max_letters_per_sec, P4.min_letters)


def test_take_far_too_short_for_its_text_is_flagged():
    text = _text_with_letters(300)

    shortfall = _shortfall(text, 10.0)  # 30 letters/s

    assert shortfall == pytest.approx(1 - 10.0 / (300 / 21.5))


def test_fast_but_complete_take_passes():
    text = _text_with_letters(300)

    assert _shortfall(text, 300 / 19.0) is None  # the fastest full take observed


def test_short_text_never_flagged():
    text = "Run, now."

    assert spoken_letters(text) < P4.min_letters
    assert _shortfall(text, 0.1) is None


def test_letters_ignore_spaces_and_punctuation():
    assert spoken_letters('"Go," she said -- 2 times.') == 15


def test_wav_duration_reads_the_header(tmp_path):
    path = tmp_path / "take.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 36000)

    assert wav_duration(path) == 1.5
