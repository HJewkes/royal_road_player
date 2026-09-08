"""Tests for the phoneme-first scan ordering in scripts/scan_defects.py.

No models load here: the phoneme recognizer and both Whisper services are stubs,
and the "audio" phones are built from espeak-ng's G2P of the source text.
"""
import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.validation.phonemes import g2p_sentence

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "scan_defects.py"
_spec = importlib.util.spec_from_file_location("scan_defects", _SCRIPT)
scan_defects = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_defects)

espeak = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng not installed")

CLEAN_TEXT = "the match in Salford ended"
BAD_TEXT = "the crowd in Wrexham roared"


@dataclass
class FakeChunk:
    index: int
    text: str
    audio_path: Path
    has_audio: bool = True


class FakeDiscovery:
    def __init__(self, chunks):
        self._chunks = chunks

    def list_chunks(self, fiction_id, book, chapter):
        return self._chunks


class FakeRecognizer:
    """Serves canned phone strings keyed by wav path."""

    def __init__(self, phones_by_path):
        self._phones = phones_by_path

    def recognize_wav(self, path):
        return self._phones[str(path)]


class FakeSTT:
    """Serves canned rich transcripts and records which wavs it was asked for."""

    def __init__(self, rich_by_path):
        self._rich = rich_by_path
        self.calls = []

    def transcribe_rich(self, path):
        self.calls.append(Path(path).name)
        return self._rich.get(str(path))


def _rich(pairs):
    return {
        "text": " ".join(w for w, _ in pairs),
        "segments": [],
        "words": [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "probability": p}
                  for i, (w, p) in enumerate(pairs)],
    }


def _fixture(tmp_path):
    """Two chunks: one whose audio matches its text, one with 'Wrexham' garbled."""
    clean_wav, bad_wav = tmp_path / "chunk_001.wav", tmp_path / "chunk_002.wav"
    bad_parts = g2p_sentence(BAD_TEXT)
    bad_parts[3] = "zzzzxq"
    phones = {str(clean_wav): "".join(g2p_sentence(CLEAN_TEXT)),
              str(bad_wav): "".join(bad_parts)}
    heard = _rich([("the", 0.98), ("crowd", 0.97), ("in", 0.98),
                   ("Zorptrix", 0.3), ("roared", 0.96)])
    chunks = [FakeChunk(1, CLEAN_TEXT, clean_wav), FakeChunk(2, BAD_TEXT, bad_wav)]
    return chunks, FakeRecognizer(phones), {str(bad_wav): heard}


def _scan(tmp_path, min_sev=0.35):
    chunks, recognizer, heard = _fixture(tmp_path)
    base_stt, confirm_stt = FakeSTT(heard), FakeSTT(heard)
    findings, n_chunks = scan_defects._scan_chapter(
        "124774", 8, 2, base_stt, confirm_stt, FakeDiscovery(chunks),
        min_sev, recognizer,
    )
    return findings, n_chunks, base_stt


@espeak
def test_whisper_runs_only_on_phoneme_flagged_chunks(tmp_path):
    """The detector is the phoneme pass: a chunk whose audio matches its text
    must never reach Whisper, however Whisper might have transcribed it."""
    findings, n_chunks, base_stt = _scan(tmp_path)
    assert n_chunks == 2
    assert base_stt.calls == ["chunk_002.wav"]
    assert {f["chunk"] for f in findings} == {2}


@espeak
def test_flagged_chunk_keeps_readable_heard_text_and_schema(tmp_path):
    """Whisper is still the describer, so survivors carry heard words and a
    timestamp alongside the phoneme verdict, under the original finding keys."""
    findings, _, _ = _scan(tmp_path)
    row = next(f for f in findings if f["expected"] == "Wrexham")
    assert row["heard"] == "Zorptrix"
    assert row["audio_start"] == 1.5
    assert row["phoneme_source"] == "xtts"
    assert set(row) >= {
        "fiction_id", "book", "chapter", "chunk", "wav", "kind", "expected",
        "heard", "severity", "causes", "audio_start", "audio_end", "context",
        "phoneme_source", "phoneme_distance", "actual_phones", "expected_phones",
    }


@espeak
def test_targets_keep_three_letter_words_and_skip_shorter(tmp_path):
    """Real defects live on 3-letter words (the "Dye Hard" mangle), so they are
    scored; 1-2 letter words stay out, where phone distance is a coin flip."""
    assert scan_defects._chunk_targets(BAD_TEXT) == ["the", "crowd", "Wrexham", "roared"]


@espeak
def test_three_letter_mangle_is_flagged(tmp_path):
    """Regression (DoF book 8 ch 2 chunk 646, "Dye Hard"): a 3-letter word read
    as something else must reach the report, not be dropped before scoring."""
    text = '"Dye Hard," I said.'
    parts = g2p_sentence(text)
    parts[0] = "ɡɹu"  # the audio says something else entirely
    verdicts = {v["word"].lower(): v for v in scan_defects._detect(
        FakeChunk(646, text, Path("x.wav")),
        FakeRecognizer({"x.wav": "".join(parts)}),
    )[0]}
    assert verdicts["dye"]["source"] == "xtts"


@espeak
def test_three_letter_word_needs_more_than_one_wrong_phone(tmp_path):
    """A single-phone slip on a 3-letter word is within G2P disagreement, so the
    short-word band keeps it out of the report."""
    text = '"Dye Hard," I said.'
    parts = g2p_sentence(text)
    parts[0] = "dɛɪ"  # one phone off
    verdicts = {v["word"].lower(): v for v in scan_defects._detect(
        FakeChunk(646, text, Path("x.wav")),
        FakeRecognizer({"x.wav": "".join(parts)}),
    )[0]}
    assert verdicts["dye"]["distance"] < 0.7
    assert verdicts["dye"]["source"] == "whisper"
