"""Tests for self-healing synthesis (synthesize_verified) retry logic.

Uses fakes for the TTS engine and phoneme recognizer and stubs the hallucination
detector, so the re-roll behaviour is tested without loading any models.
"""

from pathlib import Path

import pytest

from src.tts import verified
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
