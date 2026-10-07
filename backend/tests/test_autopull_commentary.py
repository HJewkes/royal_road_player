"""Tests for autopull.sh's commentary check failing closed.

A chapter whose commentary check did not produce a verdict must not be
generated: shipping it could narrate the author's sign-off. autopull.sh is
sourced with the backend calls stubbed; detect_commentary runs for real against
a fake claude executable, and apply_commentary.py runs for real too.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_AUTOPULL = _REPO / "scripts" / "autopull.sh"

_FAKE_CLAUDE = """#!/bin/sh
pwd >> "$TMP/claude_cwd"
printf '%s\\n' "$@" > "$TMP/claude_argv"
printf '%s' "$FAKE_OUT"
exit "${FAKE_STATUS:-0}"
"""

_HARNESS = """
set -uo pipefail
source "$AUTOPULL"

SCRIPT_DIR="$(dirname "$AUTOPULL")"
PROJECT_DIR="$TMP"
FICTION_ID=1
LOG_FILE="$TMP/log"
PYTHON="$TEST_PYTHON"
TAIL_REPAIR_LIMIT=0
CHUNKS="$TMP/data/books/1/book_8/chapters/chapter_10/chunks"

record() { echo "$*" >> "$TMP/calls"; }
download_chapters() { :; }
render_tables() { :; }
normalize_and_chunk() { record "normalize_and_chunk $*"; }
find_interrupted_chapters() { echo "$INTERRUPTED"; }
find_new_chapters() { echo "$NEW_CHAPTERS"; }
export_chapter() { record "export_chapter $*"; }
publish_feed() { record "publish_feed"; }
notify() { record "notify $1"; }
generate_audio() {
  record "generate_audio $*"
  for f in "$CHUNKS"/*.txt; do : > "${f%.txt}.wav"; done
}
if [ "${STUB_DETECT:-0}" = "1" ]; then
  detect_commentary() { record "detect_commentary $*"; return "${DETECT_STATUS:-0}"; }
fi

SUMMARY=""
$ENTRY
"""

_FAILED = "notify Audiobook commentary check failed"


def _chapter_dir(tmp_path: Path) -> Path:
    return tmp_path / "data/books/1/book_8/chapters/chapter_10"


def _run(tmp_path: Path, entry: str, wavs: int = 0, **env: str) -> list[str]:
    chunks = _chapter_dir(tmp_path) / "chunks"
    chunks.mkdir(parents=True, exist_ok=True)
    (_chapter_dir(tmp_path) / "normalized.txt").write_text("Story one.\n\nStory two.\n")
    for i in (1, 2):
        (chunks / f"{i:03d}.txt").write_text(f"Story {i}.")
        if i <= wavs:
            (chunks / f"{i:03d}.wav").write_bytes(b"RIFF")
    fake = tmp_path / "bin" / "claude"
    fake.parent.mkdir(exist_ok=True)
    fake.write_text(_FAKE_CLAUDE)
    fake.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)

    result = subprocess.run(
        ["bash", "-c", _HARNESS],
        env={
            "PATH": f"{fake.parent}:/usr/bin:/bin",
            "HOME": str(home),
            "TMP": str(tmp_path),
            "AUTOPULL": str(_AUTOPULL),
            "TEST_PYTHON": sys.executable,
            "INTERRUPTED": "",
            "NEW_CHAPTERS": "",
            "ENTRY": entry,
            **env,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = tmp_path / "calls"
    return calls.read_text().splitlines() if calls.exists() else []


def _process_new_chapter(tmp_path: Path, **env: str) -> list[str]:
    return _run(tmp_path, "process_book 8", NEW_CHAPTERS="10", **env)


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"FAKE_STATUS": "1", "FAKE_OUT": "[]"}, id="claude-exits-non-zero"),
        pytest.param({"FAKE_OUT": "I could not read the chunks."}, id="answer-is-not-json"),
        pytest.param({"CLAUDE_BIN": "/nonexistent/claude"}, id="claude-is-missing"),
    ],
)
def test_failed_commentary_check_holds_the_chapter_before_generation(tmp_path, env):
    calls = _process_new_chapter(tmp_path, **env)

    assert calls == ["normalize_and_chunk 8 10", _FAILED]
    assert not (_chapter_dir(tmp_path) / "commentary.json").exists()
    assert "commentary check failed for book 8 chapter 10" in (tmp_path / "log").read_text()


def test_clean_verdict_records_the_check_and_generates(tmp_path):
    calls = _process_new_chapter(tmp_path, FAKE_OUT="```json\n[]\n```")

    record = json.loads((_chapter_dir(tmp_path) / "commentary.json").read_text())
    assert record["removed"] == []
    assert calls == [
        "normalize_and_chunk 8 10",
        "generate_audio 8 10",
        "export_chapter 8 10",
        "publish_feed",
    ]


def test_claude_runs_headless_from_outside_the_repo_and_home(tmp_path):
    _process_new_chapter(tmp_path, FAKE_OUT="{}")

    argv = (tmp_path / "claude_argv").read_text().splitlines()
    assert argv[0] == "-p"
    assert {"--strict-mcp-config", "--no-session-persistence"} <= set(argv)
    assert "--bare" not in argv
    for cwd in (tmp_path / "claude_cwd").read_text().splitlines():
        assert not Path(cwd).is_relative_to(_REPO)
        assert not Path(cwd).is_relative_to(tmp_path / "home")


def test_resume_at_chunk_holds_the_chapter_when_the_check_fails(tmp_path):
    calls = _run(tmp_path, "resume_interrupted 8", INTERRUPTED="10:chunk:0:0", FAKE_STATUS="1")

    assert calls == ["normalize_and_chunk 8 10", _FAILED]


def test_resume_at_generate_without_audio_or_record_checks_commentary_first(tmp_path):
    calls = _run(
        tmp_path, "resume_interrupted 8", INTERRUPTED="10:generate:0:2", STUB_DETECT="1"
    )

    assert calls[:2] == ["detect_commentary 8 10", "generate_audio 8 10"]


def test_resume_at_generate_with_a_record_goes_straight_to_generation(tmp_path):
    _chapter_dir(tmp_path).mkdir(parents=True)
    (_chapter_dir(tmp_path) / "commentary.json").write_text('{"version": 1, "removed": []}')

    calls = _run(
        tmp_path, "resume_interrupted 8", INTERRUPTED="10:generate:0:2", STUB_DETECT="1"
    )

    assert calls[0] == "generate_audio 8 10"


def test_resume_at_generate_holds_the_chapter_when_the_check_fails(tmp_path):
    calls = _run(tmp_path, "resume_interrupted 8", INTERRUPTED="10:generate:0:2", FAKE_STATUS="1")

    assert calls == [_FAILED]


def test_resume_at_generate_with_audio_never_runs_detection(tmp_path):
    """Detection can delete chunks; once some have audio, that would throw away
    rendered work, so the gap is only reported."""
    calls = _run(
        tmp_path,
        "resume_interrupted 8",
        wavs=1,
        INTERRUPTED="10:generate:1:2",
        STUB_DETECT="1",
    )

    assert "detect_commentary 8 10" not in calls
    assert calls[0] == "generate_audio 8 10"
    assert "has audio but no commentary record" in (tmp_path / "log").read_text()
