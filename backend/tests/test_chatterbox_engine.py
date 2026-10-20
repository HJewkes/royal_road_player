"""ChatterboxEngine against a fake worker interpreter.

The fake stands in for the venv-chatterbox python: it runs the real worker's
protocol plumbing (chatterbox_worker.main) with a renderer that loads no model.
It records each request and its pid next to the output wav, and it prints to
stdout the way the model libraries do.
"""

import json
import os
import signal
import stat
import sys
from pathlib import Path

import pytest

from src.tts.chatterbox import ChatterboxEngine, ChatterboxUnavailable

FAKE_WORKER = '''#!{python}
import importlib.util, json, os, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("worker", sys.argv[2])
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class FakeRenderer:
    sample_rate = 24000

    def __init__(self, args):
        print("loaded PerthNet")
        os.write(1, b"native library banner\\n")

    def render(self, request):
        print("sampling 100%")
        Path(request["out"]).write_bytes(b"wav")
        Path(request["out"] + ".json").write_text(json.dumps({{**request, "pid": os.getpid()}}))
        return {{"audio_s": 1.0, "raw_lufs": -23.0, "synth_s": 0.1}}


worker.main(sys.argv[3:], renderer_factory=FakeRenderer)
'''


@pytest.fixture
def engine(tmp_path):
    fake = tmp_path / "fake-python"
    fake.write_text(FAKE_WORKER.format(python=sys.executable))
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"wav")
    engine = ChatterboxEngine(python=str(fake), reference=str(reference), load_timeout_s=30, request_timeout_s=30)
    yield engine
    engine.close()


def _recorded(path: Path) -> dict:
    return json.loads(Path(str(path) + ".json").read_text())


def test_engine_sends_p4_params_and_seed(engine, tmp_path):
    path, _ = engine.synthesize("The red fox ran home.", tmp_path / "out" / "007.wav", seed=1006)

    request = _recorded(path)
    assert request["seed"] == 1006
    assert {key: request[key] for key in ("cfg_weight", "exaggeration", "temperature")} == {
        "cfg_weight": 0.3, "exaggeration": 0.5, "temperature": 0.8,
    }
    assert {key: request[key] for key in ("min_p", "repetition_penalty", "top_p")} == {
        "min_p": 0.05, "repetition_penalty": 1.2, "top_p": 1.0,
    }
    assert (request["target_lufs"], request["trailing_pad_s"]) == (-20.0, 0.25)


def test_override_replaces_one_param_and_keeps_the_rest(engine, tmp_path):
    path, _ = engine.synthesize("A calm sea.", tmp_path / "a.wav", seed=1, temperature=0.7)

    request = _recorded(path)
    assert (request["temperature"], request["cfg_weight"]) == (0.7, 0.3)


def test_engine_respawns_after_worker_exit(engine, tmp_path):
    first, _ = engine.synthesize("One small boat.", tmp_path / "1.wav", seed=1)
    os.kill(_recorded(first)["pid"], signal.SIGKILL)

    second, _ = engine.synthesize("Two small boats.", tmp_path / "2.wav", seed=2)

    assert second.read_bytes() == b"wav"
    assert _recorded(second)["pid"] != _recorded(first)["pid"]


def test_worker_protocol_survives_library_prints(engine, tmp_path):
    path, _ = engine.synthesize("Birds sang at dawn.", tmp_path / "b.wav", seed=3)

    assert path.read_bytes() == b"wav"


@pytest.mark.parametrize("python", ["", "/nonexistent/venv-chatterbox/bin/python"])
def test_missing_interpreter_raises_clear_error(python, tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"wav")

    with pytest.raises(ChatterboxUnavailable, match="AUDIOBOOK_CHATTERBOX_PYTHON"):
        ChatterboxEngine(python=python, reference=str(reference))
