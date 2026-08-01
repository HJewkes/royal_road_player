"""Regression test for the MPS-fallback bug: a single chunk hitting an
unsupported MPS op used to permanently strand the model on CPU, making
every subsequent chunk in the queue ~30x slower.
"""

import wave
from pathlib import Path

import pytest

from src.tts.xtts import XTTSEngine


def _write_silent_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)


class FakeCoquiTTS:
    """Stands in for TTS.api.TTS, tracking device moves and failing the
    first call on 'mps' with a realistic MPS-unsupported-op error."""

    def __init__(self):
        self.devices = []
        self.calls = 0

    def to(self, device):
        self.devices.append(device)

    def tts_to_file(self, *, file_path, **kw):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError(
                "Output channels > 65536 not supported at the MPS device."
            )
        _write_silent_wav(Path(file_path))


@pytest.fixture
def engine(tmp_path):
    eng = XTTSEngine(voice_sample=str(tmp_path / "voice.wav"))
    _write_silent_wav(Path(eng.voice_sample))
    eng._tts = FakeCoquiTTS()
    eng._device = "mps"
    eng._loaded = True
    return eng


def test_mps_failure_retries_only_the_bad_chunk_on_cpu(engine, tmp_path):
    out = tmp_path / "001.wav"

    engine.synthesize("Hi boss, said Pascal.", out)

    # First attempt (mps) failed, retry succeeded on cpu.
    assert engine._tts.calls == 2
    assert out.exists()


def test_model_is_restored_to_mps_after_a_cpu_retry(engine, tmp_path):
    engine.synthesize("Hi boss, said Pascal.", tmp_path / "001.wav")

    # The fake's device history should end back on mps, not stranded on cpu.
    assert engine._tts.devices[-1] == "mps"
    assert engine._device == "mps"


def test_subsequent_chunks_are_not_forced_onto_cpu(engine, tmp_path):
    engine.synthesize("Hi boss, said Pascal.", tmp_path / "001.wav")
    calls_after_first = engine._tts.calls

    # Second chunk succeeds on the first (mps) attempt now that the model
    # was restored — no extra retry call.
    engine.synthesize("A perfectly ordinary sentence.", tmp_path / "002.wav")

    assert engine._tts.calls == calls_after_first + 1
    assert engine._tts.devices[-1] == "mps"
