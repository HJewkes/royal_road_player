"""Tests for self-healing synthesis (synthesize_verified) retry logic.

Uses fakes for the TTS engine and phoneme recognizer and stubs the hallucination
detector, so the re-roll behaviour is tested without loading any models.
"""

import os
import wave
from pathlib import Path

import pytest

from src.tts import verified
from src.tts.profiles import P4
from src.tts.verified import synthesize_verified


class FakeTTS:
    def __init__(self):
        self.calls = 0

    def synthesize(self, text, out, **kw):
        self.calls += 1
        Path(out).write_bytes(b"RIFFfake")
        return Path(out), 1.5


class FakeRecog:
    def recognize(self, samples):
        return "phones"


@pytest.fixture(autouse=True)
def _no_load_slice(monkeypatch):
    monkeypatch.setattr(verified, "load_slice", lambda *a, **k: None)


def _stub_detect(monkeypatch, sequence):
    seq = list(sequence)
    monkeypatch.setattr(verified, "detect_hallucinations", lambda *a, **k: seq.pop(0))


def test_clean_first_take_no_reroll(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[]])  # clean immediately
    tts, out = FakeTTS(), tmp_path / "o.wav"
    path, dur = synthesize_verified(tts, "hi", out, recognizer=FakeRecog(), retries=5)
    assert path == out and out.exists() and dur == 1.5
    assert tts.calls == 1


def test_rerolls_until_clean(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [
        [{"severity": 0.5, "length": 6}],
        [{"severity": 0.4, "length": 6}],
        [],  # third take is clean
    ])
    tts, out = FakeTTS(), tmp_path / "o.wav"
    path, dur = synthesize_verified(tts, "hi", out, recognizer=FakeRecog(), retries=5)
    assert out.exists()
    assert tts.calls == 3


def test_keeps_least_severe_when_never_clean(monkeypatch, tmp_path):
    # retries=2 -> 3 attempts, none clean; best severity is attempt 2 (0.3).
    _stub_detect(monkeypatch, [
        [{"severity": 0.6, "length": 8}],
        [{"severity": 0.3, "length": 6}],
        [{"severity": 0.5, "length": 7}],
    ])
    tts, out = FakeTTS(), tmp_path / "o.wav"
    path, dur = synthesize_verified(tts, "hi", out, recognizer=FakeRecog(), retries=2)
    assert out.exists()
    assert tts.calls == 3


def test_falls_back_to_single_take_without_recognizer(monkeypatch, tmp_path):
    # If the recognizer can't be obtained, degrade to a plain single synthesis.
    monkeypatch.setattr(verified, "get_phoneme_recognizer",
                        lambda: (_ for _ in ()).throw(RuntimeError("no model")))
    tts, out = FakeTTS(), tmp_path / "o.wav"
    path, dur = synthesize_verified(tts, "hi", out, recognizer=None, retries=5)
    assert out.exists() and dur == 1.5
    assert tts.calls == 1


def _open_fd_count() -> int:
    """Descriptors held by this process (/dev/fd works on macOS and Linux)."""
    return len(os.listdir("/dev/fd"))


def test_takes_do_not_leak_descriptors_across_chunks(monkeypatch, tmp_path):
    """A chapter is hundreds of chunks; one leaked descriptor per take exhausts
    the process limit mid-generation and kills the run."""
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    monkeypatch.setattr(verified.tempfile, "tempdir", str(tmpdir))
    _stub_detect(monkeypatch, [[]] * 25)

    before = _open_fd_count()
    for i in range(25):
        synthesize_verified(FakeTTS(), "hi", tmp_path / f"o{i}.wav",
                            recognizer=FakeRecog(), retries=5)
    assert _open_fd_count() == before


def test_takes_are_deleted_after_the_winner_is_copied_out(monkeypatch, tmp_path):
    """Including the re-rolls — otherwise the temp dir grows without bound."""
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    monkeypatch.setattr(verified.tempfile, "tempdir", str(tmpdir))
    _stub_detect(monkeypatch, [
        [{"severity": 0.6, "length": 8}],
        [{"severity": 0.3, "length": 6}],
        [],
    ])
    out = tmp_path / "o.wav"
    synthesize_verified(FakeTTS(), "hi", out, recognizer=FakeRecog(), retries=5)

    assert out.exists()
    assert list(tmpdir.iterdir()) == []


# 330 letters in 11 sentences, written for this test: at most 21.5 letters/s, so
# a full take lasts at least 15.3 s of speech.
LONG_TEXT = "The green boat drifted far out to sea. " * 11


class SeededTTS:
    """A Chatterbox-like engine: seeded, P4 profile, real wavs of scripted lengths."""

    profile = P4

    def __init__(self, speech_seconds):
        self.speech_seconds = list(speech_seconds)
        self.seeds = []

    def synthesize(self, text, out, seed=None, **kw):
        self.seeds.append(seed)
        audio_s = self.speech_seconds.pop(0) + P4.trailing_pad_s
        with wave.open(str(out), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(1000)
            wav.writeframes(b"\0\0" * round(audio_s * 1000))
        return Path(out), 0.5  # generation wall time, unrelated to audio length


def _kept_seconds(out):
    with wave.open(str(out), "rb") as wav:
        return wav.getnframes() / wav.getframerate() - P4.trailing_pad_s


def test_reroll_uses_a_new_seed_each_attempt(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[{"severity": 0.5, "length": 6}]] * 2 + [[]])
    tts = SeededTTS([18.0, 18.0, 18.0])

    synthesize_verified(tts, LONG_TEXT, tmp_path / "o.wav", recognizer=FakeRecog(), seed=1004)

    assert tts.seeds == [1004, 1004 + verified.SEED_STRIDE, 1004 + 2 * verified.SEED_STRIDE]


def test_early_stopped_take_is_rerolled_and_full_take_kept(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[], []])
    tts, out = SeededTTS([9.0, 18.0]), tmp_path / "o.wav"

    synthesize_verified(tts, LONG_TEXT, out, recognizer=FakeRecog(), seed=1)

    assert len(tts.seeds) == 2
    assert _kept_seconds(out) == pytest.approx(18.0)


def test_never_keeps_truncated_take_over_hallucinated_one(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[], [{"severity": 0.9, "length": 12}], []])
    tts, out = SeededTTS([9.0, 18.0, 12.0]), tmp_path / "o.wav"

    synthesize_verified(tts, LONG_TEXT, out, recognizer=FakeRecog(), retries=2, seed=1)

    assert _kept_seconds(out) == pytest.approx(18.0)


def test_least_truncated_take_kept_when_every_take_stops_early(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[], [], []])
    tts, out = SeededTTS([6.0, 12.0, 9.0]), tmp_path / "o.wav"

    synthesize_verified(tts, LONG_TEXT, out, recognizer=FakeRecog(), retries=2, seed=1)

    assert _kept_seconds(out) == pytest.approx(12.0)


def test_xtts_guard_is_off(monkeypatch, tmp_path):
    _stub_detect(monkeypatch, [[]])
    tts = SeededTTS([3.0])
    tts.profile = None

    synthesize_verified(tts, LONG_TEXT, tmp_path / "o.wav", recognizer=FakeRecog())

    assert len(tts.seeds) == 1
