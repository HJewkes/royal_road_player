"""Tests for autopull.sh's partial-generation recovery path.

autopull.sh is sourced rather than executed (its main() self-executes only when
run directly), so these drive resume_interrupted and process_book with the
pipeline calls stubbed out — no backend, no TTS, no network. What matters is
which stage a resumed chapter re-enters at, and that a chapter with missing chunk
audio is never exported, on the first run or a later one.
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
notify() { record "notify $1"; }
download_chapters() { record "download_chapters $*"; }
render_tables() { record "render_tables $*"; }
find_interrupted_chapters() { echo "$INTERRUPTED"; }
find_new_chapters() { echo "$NEW_CHAPTERS"; }
generate_audio() {
  record "generate_audio $*"
  [ "${GENERATE_SUCCEEDS:-1}" = "1" ] || return 0
  shopt -s nullglob
  for f in "$CHUNKS"/*.txt; do : > "${f%.txt}.wav"; done
  shopt -u nullglob
}

SUMMARY=""
$ENTRY
"""


def _run(
    tmp_path: Path,
    interrupted: str,
    texts: int,
    wavs: int,
    succeeds: str = "1",
    entry: str = "resume_interrupted 8",
    new_chapters: str = "",
):
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
            "NEW_CHAPTERS": new_chapters,
            "GENERATE_SUCCEEDS": succeeds,
            "ENTRY": entry,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls_file = tmp_path / "calls"
    return calls_file.read_text().splitlines() if calls_file.exists() else []


def test_resume_at_generate_skips_straight_to_generation(tmp_path):
    calls = _run(tmp_path, "10:generate:5:12", texts=12, wavs=5)
    assert calls == ["generate_audio 8 10", "export_chapter 8 10", "publish_feed"]


def test_resume_at_chunk_rebuilds_chunks_first(tmp_path):
    calls = _run(tmp_path, "10:chunk:0:0", texts=0, wavs=0)
    assert calls[:3] == [
        "normalize_and_chunk 8 10",
        "detect_commentary 8 10",
        "generate_audio 8 10",
    ]


def test_resume_at_export_only_exports(tmp_path):
    calls = _run(tmp_path, "10:export:12:12", texts=12, wavs=12)
    assert calls == ["export_chapter 8 10", "publish_feed"]


def test_chapter_with_missing_chunk_audio_is_not_exported(tmp_path):
    """Generation finishing with chunks still unrendered means they failed hard;
    exporting would ship silent holes and mark the chapter complete forever."""
    calls = _run(tmp_path, "10:generate:5:12", texts=12, wavs=5, succeeds="0")
    assert calls == ["generate_audio 8 10", "notify Audiobook chapter blocked"]
    assert "still missing chunk audio after generation (5/12)" in (tmp_path / "log").read_text()


def test_first_run_with_missing_chunk_audio_is_not_exported(tmp_path):
    """Same hole, first time through: a new chapter must not export either, so the
    next tick sees it as interrupted rather than completed."""
    calls = _run(
        tmp_path,
        "",
        texts=12,
        wavs=5,
        succeeds="0",
        entry="process_book 8",
        new_chapters="10",
    )
    assert "export_chapter 8 10" not in calls
    assert "publish_feed" not in calls
    assert "notify Audiobook chapter blocked" in calls


def test_first_run_exports_a_complete_chapter(tmp_path):
    calls = _run(tmp_path, "", texts=12, wavs=5, entry="process_book 8", new_chapters="10")
    assert calls[-3:] == ["generate_audio 8 10", "export_chapter 8 10", "publish_feed"]


def test_nothing_interrupted_does_nothing(tmp_path):
    assert _run(tmp_path, "", texts=12, wavs=12) == []


_DETECT_HARNESS = """
set -uo pipefail
source "$AUTOPULL"
PROJECT_DIR="$TMP"
FICTION_ID=1
LOG_FILE="$TMP/log"
claude() { echo "claude" >> "$TMP/calls"; echo '{}'; }
apply_commentary() { echo "apply_commentary" >> "$TMP/calls"; }
detect_commentary 8 10
"""


def _run_detect(tmp_path: Path) -> tuple[str, list[str]]:
    chunks = tmp_path / "data/books/1/book_8/chapters/chapter_10/chunks"
    chunks.mkdir(parents=True)
    (chunks / "001.txt").write_text("story")
    result = subprocess.run(
        ["bash", "-c", _DETECT_HARNESS],
        env={"PATH": "/usr/bin:/bin", "TMP": str(tmp_path), "AUTOPULL": str(_AUTOPULL)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = tmp_path / "calls"
    return result.stdout, (calls.read_text().splitlines() if calls.exists() else [])


def test_detection_is_skipped_when_decisions_are_already_on_disk(tmp_path):
    """The removals live in normalized.txt and commentary.json, so the chunks are
    already clean — asking Claude again costs money and can only change its mind."""
    chapter = tmp_path / "data/books/1/book_8/chapters/chapter_10"
    chapter.mkdir(parents=True)
    (chapter / "commentary.json").write_text('{"version": 1, "removed": []}')

    stdout, calls = _run_detect(tmp_path)

    assert "skipping detection for chapter 10" in stdout
    assert calls == []


def test_detection_runs_when_no_decisions_are_recorded(tmp_path):
    stdout, calls = _run_detect(tmp_path)

    assert "skipping detection" not in stdout
    assert calls == ["claude", "claude", "apply_commentary"]


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
