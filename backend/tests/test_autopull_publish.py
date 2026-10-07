"""Tests for autopull.sh's safe-run switch around the feed publish step.

AUTOPULL_PUBLISH=0 lets a host that already holds live R2 credentials run the
whole pipeline without uploading. autopull.sh is sourced, not executed, and
$PYTHON is a fake that records its argv, so publish_feed.py never runs.
"""
import subprocess
from pathlib import Path

_AUTOPULL = Path(__file__).resolve().parents[2] / "scripts" / "autopull.sh"

_HARNESS = """
set -uo pipefail
source "$AUTOPULL"

LOG_FILE="$TMP/log"
PYTHON="$TMP/fake-python"
publish_feed
"""

_FAKE_PYTHON = """#!/bin/sh
printf '%s\\n' "$@" > "$TMP/argv"
"""


def _publish(tmp_path: Path, publish: str | None) -> tuple[list[str], str]:
    fake = tmp_path / "fake-python"
    fake.write_text(_FAKE_PYTHON)
    fake.chmod(0o755)
    env = {"PATH": "/usr/bin:/bin", "TMP": str(tmp_path), "AUTOPULL": str(_AUTOPULL)}
    if publish is not None:
        env["AUTOPULL_PUBLISH"] = publish

    result = subprocess.run(
        ["bash", "-c", _HARNESS], env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    argv = (tmp_path / "argv").read_text().split()
    return argv, (tmp_path / "log").read_text()


def test_publish_off_builds_feeds_without_uploading(tmp_path):
    argv, log = _publish(tmp_path, "0")

    assert argv[0].endswith("publish_feed.py")
    assert "--no-upload" in argv
    assert "publishing off" in log


def test_publish_defaults_on_when_unset(tmp_path):
    argv, log = _publish(tmp_path, None)

    assert argv[0].endswith("publish_feed.py")
    assert "--no-upload" not in argv
    assert "publishing off" not in log


def test_publish_on_when_set_to_one(tmp_path):
    argv, _log = _publish(tmp_path, "1")

    assert "--no-upload" not in argv
