"""Tests for autopull.sh's partial-generation recovery path.

autopull.sh is sourced rather than executed (its main() self-executes only when
run directly), so these drive resume_interrupted with the pipeline calls stubbed
out — no backend, no TTS, no network. What matters is which stage a resumed
chapter re-enters at, and that a chapter with holes is never exported.
"""
import subprocess
from pathlib import Path

import pytest

_AUTOPULL = Path(__file__).resolve().parents[2] / "scripts" / "autopull.sh"

_HARNESS = """
set -uo pipefail
source "$AUTOPULL"

PROJECT_DIR="$TMP"
FICTION_ID=1
LOG_FILE="$TMP/log"
STATUS_FILE="$TMP/status"
CHUNKS="$TMP/data/books/1/book_8/chapters/chapter_10/chunks"

record() { echo "$*" >> "$TMP/calls"; }
normalize_and_chunk() { record "normalize_and_chunk $*"; }
detect_commentary() { record "detect_commentary $*"; }
export_chapter() { record "export_chapter $*"; }
publish_feed() { record "publish_feed"; }
find_interrupted_chapters() { echo "$INTERRUPTED"; }
generate_audio() {
  record "generate_audio $*"
  [ "${GENERATE_SUCCEEDS:-1}" = "1" ] || return 0
  shopt -s nullglob
  for f in "$CHUNKS"/*.txt; do touch "${f%.txt}.wav"; done
  shopt -u nullglob
}

SUMMARY=""
resume_interrupted 8
"""


def _run(tmp_path: Path, interrupted: str, texts: int, wavs: int, succeeds: str = "1"):
    chunks = tmp_path / "data/books/1/book_8/chapters/chapter_10/chunks"
    chunks.mkdir(parents=True)
    for i in range(1, texts + 1):
        (chunks / f"{i}.txt").write_text("c")
        if i <= wavs:
            (chunks / f"{i}.wav").write_bytes(b"RIFF")

    result = subprocess.run(
        ["bash", "-c", _HARNESS],
        env={
            "PATH": "/usr/bin:/bin",
            "TMP": str(tmp_path),
            "AUTOPULL": str(_AUTOPULL),
            "INTERRUPTED": interrupted,
            "GENERATE_SUCCEEDS": succeeds,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls_file = tmp_path / "calls"
    return calls_file.read_text().splitlines() if calls_file.exists() else []


def test_resume_at_generate_skips_straight_to_generation(tmp_path):
    calls = _run(tmp_path, "10:generate:205:456", texts=456, wavs=205)
    assert calls == ["generate_audio 8 10", "export_chapter 8 10", "publish_feed"]


def test_resume_at_chunk_rebuilds_chunks_first(tmp_path):
    calls = _run(tmp_path, "10:chunk:0:0", texts=0, wavs=0)
    assert calls[:3] == [
        "normalize_and_chunk 8 10",
        "detect_commentary 8 10",
        "generate_audio 8 10",
    ]


def test_resume_at_export_only_exports(tmp_path):
    calls = _run(tmp_path, "10:export:456:456", texts=456, wavs=456)
    assert calls == ["export_chapter 8 10", "publish_feed"]


def test_chapter_with_missing_chunk_audio_is_not_exported(tmp_path):
    """Generation finishing with chunks still unrendered means they failed hard;
    exporting would ship silent holes and mark the chapter complete forever."""
    calls = _run(tmp_path, "10:generate:205:456", texts=456, wavs=205, succeeds="0")
    assert calls == ["generate_audio 8 10"]
    assert "still missing chunk audio" in (tmp_path / "log").read_text()


def test_nothing_interrupted_does_nothing(tmp_path):
    assert _run(tmp_path, "", texts=456, wavs=456) == []


@pytest.mark.parametrize(
    "status, expected",
    [
        ("2026-09-07 10:00:00 exit=0", ""),
        ("2026-09-07 10:00:00 exit=3", "previous run failed"),
        ("2026-09-07 10:00:00 running pid=42", "previous run was killed"),
    ],
)
def test_report_last_status_surfaces_a_dead_previous_run(tmp_path, status, expected):
    (tmp_path / "status").write_text(status + "\n")
    script = f'source "$AUTOPULL"; LOG_FILE="$TMP/log"; STATUS_FILE="$TMP/status"; report_last_status'
    result = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": "/usr/bin:/bin", "TMP": str(tmp_path), "AUTOPULL": str(_AUTOPULL)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
