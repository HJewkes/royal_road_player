"""Tests for crash-safe writes of chapter audio.wav and its manifest."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.export import concatenator as concat_module
from src.export.concatenator import AudioConcatenator, AudioExporter

FICTION_ID = "12345"
BOOK = 1
CHAPTER = 1


@pytest.fixture
def chapter_dir(tmp_path, monkeypatch):
    """A chapter with three chunk wavs, under patched books/exports dirs."""
    settings = SimpleNamespace(
        books_dir=tmp_path / "books",
        exports_dir=tmp_path / "exports",
    )
    monkeypatch.setattr(concat_module, "get_settings", lambda: settings)
    monkeypatch.setattr("src.discovery.get_settings", lambda: settings)

    chunks_dir = (
        settings.books_dir
        / FICTION_ID
        / f"book_{BOOK}"
        / "chapters"
        / f"chapter_{CHAPTER}"
        / "chunks"
    )
    chunks_dir.mkdir(parents=True)
    for index in (1, 2, 3):
        (chunks_dir / f"{index:03d}.txt").write_text(f"chunk {index}")
        _write_wav(chunks_dir / f"{index:03d}.wav", f"audio {index}", mtime=1000.0)
    return chunks_dir.parent


@pytest.fixture
def calls(monkeypatch):
    """Stub out real audio work; record which steps ran."""
    recorded = {"concat": 0, "convert": 0}

    def fake_concat(self, audio_files, output_path):
        recorded["concat"] += 1
        output_path.write_bytes(b"".join(f.read_bytes() for f in audio_files))
        return output_path

    def fake_convert(self, input_path, output_path, format):
        recorded["convert"] += 1
        output_path.write_bytes(input_path.read_bytes())
        return output_path

    monkeypatch.setattr(AudioConcatenator, "_write_concatenated", fake_concat)
    monkeypatch.setattr(AudioExporter, "_convert_audio", fake_convert)
    return recorded


def _write_wav(path: Path, content: str, mtime: float) -> None:
    path.write_text(content)
    os.utime(path, (mtime, mtime))


def _export(force: bool = False):
    return AudioExporter().export_chapter(FICTION_ID, BOOK, CHAPTER, force=force)


def _manifest_path(chapter_dir: Path) -> Path:
    return chapter_dir / "audio.wav.manifest.json"


def _temp_files(chapter_dir: Path) -> list[Path]:
    return list(chapter_dir.glob("*.tmp"))


def test_crash_after_the_wav_leaves_no_manifest_and_rebuilds(
    chapter_dir, calls, monkeypatch
):
    real_writer = concat_module._write_manifest
    crashing = {"enabled": True}

    def flaky_manifest(wav_path, chunks):
        if crashing["enabled"]:
            raise RuntimeError("crashed after the wav landed")
        real_writer(wav_path, chunks)

    monkeypatch.setattr(concat_module, "_write_manifest", flaky_manifest)
    with pytest.raises(RuntimeError):
        _export()
    assert (chapter_dir / "audio.wav").exists()
    assert not _manifest_path(chapter_dir).exists()

    crashing["enabled"] = False
    assert _export() is not None
    assert calls["concat"] == 2


def test_crash_before_the_wav_rename_keeps_the_previous_pair(
    chapter_dir, calls, monkeypatch
):
    assert _export() is not None
    good_wav = (chapter_dir / "audio.wav").read_bytes()
    good_manifest = _manifest_path(chapter_dir).read_text()

    def exploding_concat(self, audio_files, output_path):
        output_path.write_bytes(b"truncated")
        raise RuntimeError("crashed before the rename")

    monkeypatch.setattr(AudioConcatenator, "_write_concatenated", exploding_concat)
    _write_wav(chapter_dir / "chunks" / "002.wav", "audio 2 fixed", mtime=2000.0)
    with pytest.raises(RuntimeError):
        _export()

    assert (chapter_dir / "audio.wav").read_bytes() == good_wav
    assert _manifest_path(chapter_dir).read_text() == good_manifest


def test_successful_concatenation_leaves_no_temp_files(chapter_dir, calls):
    assert _export() is not None

    assert _temp_files(chapter_dir) == []
    assert list(chapter_dir.glob("*.manifest.json.tmp")) == []


def test_leftover_temp_files_are_cleared_before_concatenating(chapter_dir, calls):
    (chapter_dir / "audio.wav.tmp").write_bytes(b"leftover from a crashed run")

    assert _export() is not None
    assert calls["concat"] == 1
    assert _temp_files(chapter_dir) == []


def test_the_manifest_written_after_a_crash_free_run_matches_the_chunks(
    chapter_dir, calls
):
    assert _export() is not None

    manifest = json.loads(_manifest_path(chapter_dir).read_text())
    assert [c["index"] for c in manifest["chunks"]] == [1, 2, 3]
    assert _export() is not None
    assert calls["concat"] == 1
