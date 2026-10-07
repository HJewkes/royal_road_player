"""Tests for deploy/systemd/, the units that run autopull unattended on Linux.

`systemd-analyze verify` loads the units the way the user manager would, in a
throwaway HOME and runtime dir, so it needs no installed units and no session
bus. The key checks parse the files directly so they run without systemd too.
"""
import configparser
import shutil
import subprocess
from pathlib import Path

import pytest

_UNITS = Path(__file__).resolve().parents[2] / "deploy" / "systemd"
_SERVICE = _UNITS / "audiobook-autopull.service"
_FAILED = _UNITS / "audiobook-autopull-failed.service"
_TIMER = _UNITS / "audiobook-autopull.timer"
_ENV_EXAMPLE = _UNITS / "autopull.env.example"

needs_systemd = pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze not installed")


def _parse(unit: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(unit)
    return parser


def _analyze(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    home, runtime = tmp_path / "home", tmp_path / "run"
    home.mkdir()
    runtime.mkdir(mode=0o700)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "XDG_RUNTIME_DIR": str(runtime)}
    return subprocess.run(["systemd-analyze", *args], env=env, capture_output=True, text=True)


@needs_systemd
def test_units_pass_systemd_verify(tmp_path):
    result = _analyze(tmp_path, "--user", "verify", str(_SERVICE), str(_FAILED), str(_TIMER))

    assert result.returncode == 0, result.stderr
    assert _UNITS.name not in result.stderr, result.stderr


@needs_systemd
def test_timer_calendar_expression_parses(tmp_path):
    on_calendar = _parse(_TIMER)["Timer"]["OnCalendar"]

    result = _analyze(tmp_path, "calendar", on_calendar)

    assert result.returncode == 0, result.stderr
    assert "*-*-* *:01,16,31,46:00" in result.stdout


def test_service_runs_in_gpu_slice_with_raised_fd_limit():
    service = _parse(_SERVICE)["Service"]

    assert service.get("Slice") == "gpu-jobs.slice"
    assert service.get("LimitNOFILE") == "8192"
    assert service.get("TimeoutStartSec") == "infinity"


def test_service_failure_triggers_the_notifier_unit():
    assert _parse(_SERVICE)["Unit"].get("OnFailure") == _FAILED.name


def test_env_example_is_plain_key_value_in_shadow_mode():
    lines = [line for line in _ENV_EXAMPLE.read_text().splitlines() if line and not line.startswith("#")]
    pairs = dict(line.split("=", 1) for line in lines)

    assert all(key.isidentifier() and '"' not in value and "'" not in value for key, value in pairs.items())
    assert pairs["AUTOPULL_PUBLISH"] == "0"
