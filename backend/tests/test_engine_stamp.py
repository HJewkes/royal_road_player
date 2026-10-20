"""Chapter engine stamps and the TTS engine factory."""

import json
import sys

import pytest

from src.discovery import ChunkDiscovery
from src.tts import engine_stamp, get_tts_engine

XTTS = engine_stamp("xtts")
CHATTERBOX = engine_stamp("chatterbox")
CHUNKS = [(1, "The lamp was lit."), (2, "Nobody came to the door.")]


@pytest.fixture
def discovery(tmp_path):
    return ChunkDiscovery(books_dir=tmp_path)


def _chunks_dir(discovery):
    return discovery.get_chunks_dir("1", 1, 1)


def _render(discovery, index):
    chunks_dir = _chunks_dir(discovery)
    (chunks_dir / f"{index:03d}.wav").write_bytes(b"RIFF")
    (chunks_dir / f"{index + 1:03d}.error").write_text("synthesis failed")


def test_save_chunks_writes_stamp(discovery):
    discovery.save_chunks("1", 1, 1, CHUNKS, CHATTERBOX)

    stamp = json.loads((_chunks_dir(discovery) / "engine.json").read_text())
    assert stamp == {"engine": "chatterbox", "chunking": "chatterbox-450", "profile": "p4"}


def test_restamping_with_new_engine_clears_audio(discovery):
    discovery.save_chunks("1", 1, 1, CHUNKS, XTTS)
    _render(discovery, 1)

    removed = discovery.save_chunks("1", 1, 1, CHUNKS, CHATTERBOX)

    chunks_dir = _chunks_dir(discovery)
    assert removed == 2
    assert not list(chunks_dir.glob("*.wav"))
    assert not list(chunks_dir.glob("*.error"))
    assert discovery.read_engine_stamp("1", 1, 1)["engine"] == "chatterbox"


def test_stamping_a_legacy_xtts_chapter_for_chatterbox_clears_audio(discovery):
    discovery.save_chunks("1", 1, 1, CHUNKS)
    _render(discovery, 1)

    discovery.save_chunks("1", 1, 1, CHUNKS, CHATTERBOX)

    assert not list(_chunks_dir(discovery).glob("*.wav"))


def test_same_stamp_keeps_audio(discovery):
    discovery.save_chunks("1", 1, 1, CHUNKS, XTTS)
    _render(discovery, 1)

    removed = discovery.save_chunks("1", 1, 1, CHUNKS, XTTS)

    assert removed == 0
    assert (_chunks_dir(discovery) / "001.wav").exists()


def test_stamping_a_legacy_chapter_as_xtts_keeps_audio(discovery):
    discovery.save_chunks("1", 1, 1, CHUNKS)
    _render(discovery, 1)

    discovery.save_chunks("1", 1, 1, CHUNKS, XTTS)

    assert (_chunks_dir(discovery) / "001.wav").exists()


def test_missing_stamp_reads_as_legacy_xtts(discovery, monkeypatch):
    monkeypatch.setenv("AUDIOBOOK_TTS_ENGINE", "chatterbox")
    discovery.save_chunks("1", 1, 1, CHUNKS)

    assert discovery.read_engine_stamp("1", 1, 1) == {"engine": "xtts", "chunking": "xtts-250"}


def test_engine_defaults_to_xtts(monkeypatch):
    from src.config import Settings

    monkeypatch.delenv("AUDIOBOOK_TTS_ENGINE", raising=False)

    assert Settings(_env_file=None).tts_engine == "xtts"


def _chatterbox_settings(monkeypatch, **overrides):
    from src.config import Settings
    from src.tts import chatterbox, engines

    monkeypatch.setattr(engines, "_chatterbox", None)
    monkeypatch.setattr(chatterbox, "get_settings", lambda: Settings(_env_file=None, **overrides))


def test_factory_builds_chatterbox_when_its_venv_is_configured(monkeypatch, tmp_path):
    from src.tts.chatterbox import ChatterboxEngine

    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"wav")
    _chatterbox_settings(
        monkeypatch, chatterbox_python=sys.executable, chatterbox_reference_path=str(reference)
    )

    engine = get_tts_engine("chatterbox")

    assert isinstance(engine, ChatterboxEngine)
    assert get_tts_engine("chatterbox") is engine


def test_factory_refuses_chatterbox_without_its_interpreter(monkeypatch):
    from src.tts.chatterbox import ChatterboxUnavailable

    _chatterbox_settings(monkeypatch, chatterbox_python="")

    with pytest.raises(ChatterboxUnavailable, match="AUDIOBOOK_CHATTERBOX_PYTHON"):
        get_tts_engine("chatterbox")


def test_factory_rejects_unknown_engine():
    with pytest.raises(ValueError, match="Unknown TTS engine"):
        get_tts_engine("espeak")


def test_factory_returns_one_xtts_instance():
    assert get_tts_engine("xtts") is get_tts_engine("xtts")
