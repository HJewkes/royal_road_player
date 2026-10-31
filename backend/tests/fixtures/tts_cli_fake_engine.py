"""Runs scripts/tts_cli.py as a real process over a stand-in engine.

FAKE_ENGINE_MODE picks its behaviour (ok, garbage, unavailable); FAKE_ENGINE_LOG
names a file that receives one JSON line per synthesize call.
"""
import importlib.util
import json
import os
import sys
import wave
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "tts_cli.py"
_spec = importlib.util.spec_from_file_location("tts_cli", _SCRIPT)
tts_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tts_cli)

from src.tts import verified  # noqa: E402

SAMPLE_RATE = 16000
MODE = os.environ.get("FAKE_ENGINE_MODE", "ok")


def _write_silence(path, seconds=0.25):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\0\0" * int(SAMPLE_RATE * seconds))


class FakeEngine:
    def __init__(self, name):
        self.name = name

    def synthesize(self, text, output_path, seed=None, **params):
        print("> Text splitted to sentences.")
        os.write(1, b"native library chatter\n")
        with open(os.environ["FAKE_ENGINE_LOG"], "a", encoding="utf-8") as log:
            log.write(json.dumps({"engine": self.name, "text": text, "params": params}) + "\n")
        if MODE == "garbage":
            Path(output_path).write_bytes(b"not audio")
        else:
            _write_silence(output_path)
        return output_path, 0.0


def _fake_get_engine(name=None):
    if MODE == "unavailable":
        raise tts_cli.ChatterboxUnavailable("no chatterbox venv on this host")
    return FakeEngine(name)


def _no_recognizer():
    raise RuntimeError("no phoneme model in tests")


tts_cli.get_tts_engine = _fake_get_engine
verified.get_phoneme_recognizer = _no_recognizer

sys.exit(tts_cli.main())
