"""Conformance of scripts/tts_cli.py with the speech-tts commandTts stdio contract.

The CLI runs as a real process in the contract's minimal environment (no
PYTHONPATH, a foreign cwd, `python -I`, as the ssh argv runs it), over a stand-in
engine that chatters on stdout the way Coqui and native libraries do.
"""
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from src.tts import verified

_REPO = Path(__file__).resolve().parents[2]
WRAPPER = _REPO / "backend" / "tests" / "fixtures" / "tts_cli_fake_engine.py"
FAKE_SAMPLE_RATE = 16000
CORPUS_INITIALISMS = (
    "ACL", "AFC", "AMC", "EFL", "ESPN", "ITV", "PFA", "PGMOL", "USMNT", "VAR", "WBA", "WFA",
)

_spec = importlib.util.spec_from_file_location("tts_cli", _REPO / "scripts" / "tts_cli.py")
tts_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tts_cli)


class Cli:
    """Runs the CLI over the fake engine and reads back what the engine was asked."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.log = tmp_path / "engine.jsonl"

    def run(self, request, *flags, mode="ok"):
        stdin = request if isinstance(request, bytes) else json.dumps(request).encode()
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.tmp),
            "TMPDIR": str(self.tmp),
            "FAKE_ENGINE_MODE": mode,
            "FAKE_ENGINE_LOG": str(self.log),
        }
        return subprocess.run(
            [sys.executable, "-I", str(WRAPPER), *flags],
            input=stdin, capture_output=True, env=env, cwd=self.tmp, timeout=120, check=False,
        )

    def engine_calls(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def cli(tmp_path):
    return Cli(tmp_path)


def request(**overrides):
    return {"version": 1, "voice": "narrator", "text": "Hello there.", **overrides}


def assert_exactly_one_riff(data: bytes) -> wave.Wave_read:
    """The whole buffer is one RIFF/WAVE file: stray bytes on either side fail."""
    assert data[:4] == b"RIFF", data[:40]
    assert data[8:12] == b"WAVE"
    riff_size = struct.unpack("<I", data[4:8])[0]
    assert len(data) == riff_size + 8
    return wave.open(io.BytesIO(data), "rb")


def test_stdout_wav_writes_only_riff_bytes_at_the_engine_rate(cli):
    result = cli.run(request(), "--output", "stdout-wav")

    assert result.returncode == 0, result.stderr
    wav = assert_exactly_one_riff(result.stdout)
    assert wav.getframerate() == FAKE_SAMPLE_RATE
    assert wav.getnframes() > 0


def test_engine_chatter_on_stdout_reaches_stderr_instead(cli):
    result = cli.run(request(), "--output", "stdout-wav")

    assert b"Text splitted" in result.stderr
    assert b"native library chatter" in result.stderr


def test_request_without_out_dir_answers_stdout_wav_with_no_flag(cli):
    result = cli.run(request())

    assert result.returncode == 0, result.stderr
    assert_exactly_one_riff(result.stdout)


def test_request_with_out_dir_answers_one_json_object_naming_a_bare_file(cli, tmp_path):
    out_dir = tmp_path / "call"
    out_dir.mkdir()

    result = cli.run(request(outDir=str(out_dir), out=str(out_dir / "out.wav")))

    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["wav"] == "out.wav"
    assert doc["durationS"] == pytest.approx(0.25)
    assert_exactly_one_riff((out_dir / doc["wav"]).read_bytes())


def test_json_output_without_out_dir_is_refused(cli):
    result = cli.run(request(), "--output", "json")

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"outDir" in result.stderr


def test_corpus_initialisms_reach_the_engine_spelled_out(cli):
    text = " and ".join(CORPUS_INITIALISMS) + " played"

    cli.run(request(text=text))

    spoken = cli.engine_calls()[0]["text"]
    for token in CORPUS_INITIALISMS:
        assert ". ".join(token) + "." in spoken
        assert token not in spoken


def test_text_is_read_as_utf8_without_a_locale(cli):
    cli.run(json.dumps(request(text="It cost £5 — cheap."), ensure_ascii=False).encode())

    assert cli.engine_calls()[0]["text"] == "It cost £5 — cheap."


def test_speed_reaches_the_engine(cli):
    cli.run(request(speed=1.1))

    assert cli.engine_calls()[0]["params"] == {"speed": 1.1}


@pytest.mark.parametrize("overrides", [{}, {"speed": 1}], ids=["absent", "one"])
def test_default_speed_is_not_sent_to_an_engine_with_no_speed_control(cli, overrides):
    cli.run(request(voice="chatterbox", **overrides))

    assert cli.engine_calls()[0]["params"] == {}


@pytest.mark.parametrize("voice, engine", [("narrator", None), ("xtts", "xtts"), ("chatterbox", "chatterbox")])
def test_voice_selects_the_engine(cli, voice, engine):
    cli.run(request(voice=voice))

    assert cli.engine_calls()[0]["engine"] == engine


@pytest.mark.parametrize("bad", [
    pytest.param(b"not json", id="not-json"),
    pytest.param(request(version=2), id="future-version"),
    pytest.param(request(voice="alloy"), id="unknown-voice"),
    pytest.param(request(text="  "), id="blank-text"),
    pytest.param(request(language="fr-FR"), id="foreign-language"),
    pytest.param({"version": 1, "voice": "narrator", "alphabet": "ipa",
                  "tokens": [{"text": "hi", "phonemes": "haɪ"}]}, id="phoneme-tokens"),
])
def test_bad_request_fails_before_the_engine_with_nothing_on_stdout(cli, bad):
    result = cli.run(bad)

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"tts_cli:" in result.stderr
    assert not cli.log.exists()


def test_english_regional_language_is_accepted(cli):
    assert cli.run(request(language="en-US")).returncode == 0


def test_unreachable_engine_exits_with_the_unavailable_code(cli):
    result = cli.run(request(voice="chatterbox"), mode="unavailable")

    assert result.returncode == 69
    assert result.stdout == b""
    assert b"no chatterbox venv" in result.stderr


def test_engine_output_that_is_not_riff_fails_with_nothing_on_stdout(cli):
    result = cli.run(request(), mode="garbage")

    assert result.returncode == 1
    assert result.stdout == b""


class _SilentEngine:
    def __init__(self):
        self.takes = 0

    def synthesize(self, text, output_path, seed=None, **params):
        self.takes += 1
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(FAKE_SAMPLE_RATE)
            wav.writeframes(b"\0\0" * 1600)
        return output_path, 0.0


class _Recognizer:
    def recognize(self, audio):
        return "phones"


def test_babbled_take_is_rerolled_like_a_chapter_chunk(monkeypatch, tmp_path):
    engine = _SilentEngine()
    flaws = iter([[{"severity": 0.9}], []])
    monkeypatch.setattr(tts_cli, "get_tts_engine", lambda name: engine)
    monkeypatch.setattr(verified, "get_phoneme_recognizer", lambda: _Recognizer())
    monkeypatch.setattr(verified, "load_slice", lambda *a: "audio")
    monkeypatch.setattr(verified, "detect_hallucinations", lambda *a, **k: next(flaws))

    tts_cli.render(request(), tmp_path / "out.wav")

    assert engine.takes == 2
