"""Tests for rebuilding a stale chapter audio.wav on export."""

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


def test_regenerated_chunk_wav_forces_a_rebuild(chapter_dir, calls):
    assert _export() is not None
    original = (chapter_dir / "audio.wav").read_bytes()

    _write_wav(chapter_dir / "chunks" / "002.wav", "audio 2 fixed", mtime=2000.0)

    assert _export() is not None
    assert calls["concat"] == 2
    assert (chapter_dir / "audio.wav").read_bytes() != original


def test_unchanged_chunks_reuse_the_existing_audio(chapter_dir, calls):
    _export()
    assert calls["concat"] == 1

    _export()
    assert calls["concat"] == 1


def test_pruned_chunk_wavs_keep_a_legacy_audio_wav(chapter_dir, calls):
    wav_path = chapter_dir / "audio.wav"
    wav_path.write_text("legacy chapter audio")
    for chunk_wav in (chapter_dir / "chunks").glob("*.wav"):
        chunk_wav.unlink()

    assert _export() is not None
    assert calls["concat"] == 0
    assert wav_path.read_text() == "legacy chapter audio"


def test_missing_manifest_with_chunk_wavs_rebuilds(chapter_dir, calls):
    (chapter_dir / "audio.wav").write_text("legacy chapter audio")

    assert _export() is not None
    assert calls["concat"] == 1


def test_rechunking_to_fewer_chunks_rebuilds(chapter_dir, calls):
    _export()
    (chapter_dir / "chunks" / "003.wav").unlink()
    (chapter_dir / "chunks" / "003.txt").unlink()

    _export()
    assert calls["concat"] == 2
    manifest = json.loads((chapter_dir / "audio.wav.manifest.json").read_text())
    assert [c["index"] for c in manifest["chunks"]] == [1, 2]


def test_force_rebuilds_an_up_to_date_audio_wav(chapter_dir, calls):
    _export()

    _export(force=True)
    assert calls["concat"] == 2
