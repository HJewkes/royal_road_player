"""Tests for autopull.sh's notify(): ntfy push, osascript fallback, never fatal."""
import os
import subprocess
from pathlib import Path

_AUTOPULL = Path(__file__).resolve().parents[2] / "scripts" / "autopull.sh"

_HARNESS = """
set -euo pipefail
source "$AUTOPULL"
LOG_FILE="$TMP/log"
notify "$TITLE" "body text"
echo reached-end
"""


def _run(tmp_path: Path, *, url: str | None, curl_exit: int = 0, title: str = "Audiobook ok"):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "curl"
    fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "$TMP/curl_argv"\nexit {curl_exit}\n')
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "AUTOPULL": str(_AUTOPULL),
        "TMP": str(tmp_path),
        "TITLE": title,
    }
    env.pop("AUDIOBOOK_NTFY_URL", None)
    if url is not None:
        env["AUDIOBOOK_NTFY_URL"] = url
    result = subprocess.run(["bash", "-c", _HARNESS], env=env, capture_output=True, text=True)
    argv_file = tmp_path / "curl_argv"
    argv = argv_file.read_text().splitlines() if argv_file.exists() else []
    return result, argv


def test_url_set_posts_title_and_message_once(tmp_path):
    result, argv = _run(tmp_path, url="http://ntfy.invalid/topic")
    assert result.returncode == 0
    assert "http://ntfy.invalid/topic" in argv
    assert "Title: Audiobook ok" in argv
    assert "Priority: default" in argv
    assert "body text" in argv
    assert argv.count("http://ntfy.invalid/topic") == 1


def test_failed_title_gets_high_priority(tmp_path):
    _, argv = _run(tmp_path, url="http://ntfy.invalid/t", title="Audiobook autopull failed")
    assert "Priority: high" in argv


def test_blocked_title_gets_high_priority(tmp_path):
    _, argv = _run(tmp_path, url="http://ntfy.invalid/t", title="Audiobook blocked")
    assert "Priority: high" in argv


def test_url_unset_never_calls_curl(tmp_path):
    result, argv = _run(tmp_path, url=None)
    assert result.returncode == 0
    assert argv == []


def test_failing_curl_does_not_fail_the_run(tmp_path):
    result, _ = _run(tmp_path, url="http://ntfy.invalid/topic", curl_exit=7)
    assert result.returncode == 0
    assert "reached-end" in result.stdout
