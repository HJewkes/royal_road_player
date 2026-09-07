"""Regression test for the MPS-fallback bug: a single chunk hitting an
unsupported MPS op used to permanently strand the model on CPU, making
every subsequent chunk in the queue ~30x slower.
"""

import json
import subprocess
import sys
import textwrap
import types
import wave
from pathlib import Path

import pytest

from src.tts.xtts import _MPS_MAX_CONV1D_CHANNELS, XTTSEngine


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


def _fake_torch(conv1d):
    """A torch stand-in exposing just what _detect_device touches."""
    return types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
        backends=types.SimpleNamespace(
            mps=types.SimpleNamespace(is_available=lambda: True)
        ),
        zeros=lambda *shape, device=None: shape,
        nn=types.SimpleNamespace(functional=types.SimpleNamespace(conv1d=conv1d)),
    )


def _install(monkeypatch, torch):
    monkeypatch.setitem(sys.modules, "torch", torch)


def test_mps_is_rejected_when_the_speaker_encoder_conv_is_unsupported(monkeypatch):
    def conv1d(audio, weight):
        raise NotImplementedError(
            f"Output channels > {_MPS_MAX_CONV1D_CHANNELS} not supported at the MPS device."
        )

    _install(monkeypatch, _fake_torch(conv1d))

    assert XTTSEngine()._detect_device() == "cpu"


def test_mps_is_used_when_the_speaker_encoder_conv_runs(monkeypatch):
    _install(monkeypatch, _fake_torch(lambda audio, weight: None))

    assert XTTSEngine()._detect_device() == "mps"


def test_the_probe_convolves_past_the_mps_output_channel_cap(monkeypatch):
    seen = {}

    def conv1d(audio, weight):
        seen["audio"], seen["weight"] = audio, weight

    _install(monkeypatch, _fake_torch(conv1d))
    XTTSEngine()._detect_device()

    # Output length is input - kernel + 1; it must exceed the cap or the probe
    # would pass on hardware that actually fails mid-chapter.
    output_length = seen["audio"][-1] - seen["weight"][-1] + 1
    assert output_length > _MPS_MAX_CONV1D_CHANNELS


def test_the_probe_runs_once_per_load_not_once_per_chunk(monkeypatch, engine, tmp_path):
    calls = []
    _install(monkeypatch, _fake_torch(lambda audio, weight: calls.append(1)))

    engine._detect_device()
    engine.synthesize("Hi boss, said Pascal.", tmp_path / "001.wav")
    engine.synthesize("A perfectly ordinary sentence.", tmp_path / "002.wav")

    assert len(calls) == 1


def test_mps_fallback_env_var_is_set_before_torch_is_imported():
    """The var only takes effect pre-import, and xtts.py sets it at module
    scope — which only helps while nothing in the app's import chain reaches
    torch first. Assert that ordering rather than trusting it.
    """
    probe = textwrap.dedent(
        """
        import importlib.abc, json, os, sys
        seen = {}

        class Recorder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "torch":
                    seen.setdefault("env", os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK"))
                return None

        sys.meta_path.insert(0, Recorder())
        import src.api.routes  # noqa: F401
        print(json.dumps(seen))
        """
    )
    backend = str(Path(__file__).resolve().parent.parent)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "PYTHONPATH": backend}

    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, env=env, check=True
    )

    assert json.loads(result.stdout.strip().splitlines()[-1]) == {"env": "1"}
