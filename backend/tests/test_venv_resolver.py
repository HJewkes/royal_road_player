"""Tests for scripts/venv.sh, the one resolver for the project's Python venv.

The Makefile, .mcp.json and autopull.sh all run Python through it, so its
preference order ($AUDIOBOOK_VENV, then venv-cu128, then venv311) decides which
interpreter the server, the MCP server and the unattended pipeline get. Fake
venvs are tmp dirs holding a `bin/python` shell script — no real interpreter.
"""
import shutil
import subprocess
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_PATH = "/usr/bin:/bin"


def _fake_venv(root: Path, name: str) -> Path:
    python = root / name / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\necho "{name} $*"\n')
    python.chmod(0o755)
    return root / name


def _resolve(root: Path, override: str = "") -> str:
    result = subprocess.run(
        ["bash", "-c", 'source "$RESOLVER"; audiobook_venv_dir "$ROOT"'],
        env={"PATH": _PATH, "RESOLVER": str(_SCRIPTS / "venv.sh"), "ROOT": str(root), "AUDIOBOOK_VENV": override},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_cuda_venv_wins_when_both_exist(tmp_path):
    _fake_venv(tmp_path, "venv311")
    cu128 = _fake_venv(tmp_path, "venv-cu128")

    assert _resolve(tmp_path) == str(cu128)


def test_mac_venv_is_the_fallback(tmp_path):
    venv311 = _fake_venv(tmp_path, "venv311")

    assert _resolve(tmp_path) == str(venv311)


def test_env_override_beats_both_venvs(tmp_path):
    _fake_venv(tmp_path, "venv311")
    _fake_venv(tmp_path, "venv-cu128")

    assert _resolve(tmp_path, "/opt/custom") == "/opt/custom"


def test_relative_override_is_taken_from_the_project_root(tmp_path):
    assert _resolve(tmp_path, "venv-other") == str(tmp_path / "venv-other")


def test_running_it_execs_the_resolved_python_with_its_args(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(_SCRIPTS / "venv.sh", tmp_path / "scripts" / "venv.sh")
    _fake_venv(tmp_path, "venv311")
    _fake_venv(tmp_path, "venv-cu128")

    result = subprocess.run(
        ["bash", "scripts/venv.sh", "mcp_server/audiobook_mcp.py", "--flag"],
        cwd=tmp_path,
        env={"PATH": _PATH},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "venv-cu128 mcp_server/audiobook_mcp.py --flag"


def test_running_it_with_no_venv_fails_with_a_setup_hint(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(_SCRIPTS / "venv.sh", tmp_path / "scripts" / "venv.sh")

    result = subprocess.run(
        ["bash", "scripts/venv.sh", "main.py"], cwd=tmp_path, env={"PATH": _PATH}, capture_output=True, text=True
    )

    assert result.returncode == 1
    assert "make setup" in result.stderr


def _source_autopull(cwd: Path, override: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", 'source "$AUTOPULL"; echo "$PYTHON"; echo "$VENV"'],
        cwd=cwd,
        env={"PATH": _PATH, "AUTOPULL": str(_SCRIPTS / "autopull.sh"), "AUDIOBOOK_VENV": override},
        capture_output=True,
        text=True,
    )


def test_sourcing_autopull_with_no_venv_still_succeeds(tmp_path):
    result = _source_autopull(tmp_path)

    assert result.returncode == 0, result.stderr
    python, activate = result.stdout.split()
    assert python.endswith("/venv311/bin/python")
    assert activate.endswith("/venv311/bin/activate")


def test_autopull_takes_its_python_from_the_resolver(tmp_path):
    result = _source_autopull(tmp_path, "/opt/custom")

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["/opt/custom/bin/python", "/opt/custom/bin/activate"]
