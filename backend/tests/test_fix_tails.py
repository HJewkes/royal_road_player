"""Tests for the tail-artifact fix path in scripts/fix_pass.py.

No models load: TTS and the phoneme recognizer are stubs, and the "audio" phones
are built from espeak-ng's G2P of the source text so a take can be made clean,
shorter, or word-breaking on demand.
"""
import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.validation.phonemes import clean_ipa, g2p

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fix_pass.py"
_spec = importlib.util.spec_from_file_location("fix_pass", _SCRIPT)
fix_pass = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix_pass)

espeak = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng not installed")

TEXT = "we need to get him here"


@dataclass
class FakeChunk:
    index: int
    text: str
    audio_path: Path
    has_audio: bool = True


class FakeRecognizer:
    """Canned phones per wav path; unknown paths fall back to the clean rendering."""

    def __init__(self, phones_by_name, default):
        self._phones = phones_by_name
        self._default = default

    def recognize_wav(self, path, use_cache=True):
        return self._phones.get(Path(path).name, self._default)


class FakeTTS:
    """Writes an empty wav per take and records the params it was called with."""

    def __init__(self, tmp_path):
        self.calls = []
        self._tmp = tmp_path

    def synthesize(self, text, out_path, **kw):
        Path(out_path).write_bytes(b"")
        self.calls.append(kw)
        return out_path, 0.0


def _args(takes=3):
    class A:
        pass
    a = A()
    a.takes, a.limit = takes, 10
    return a


@espeak
def test_take_that_clears_the_stray_is_kept(tmp_path):
    clean = clean_ipa(g2p(TEXT))
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"")
    chunk = FakeChunk(1, TEXT, shipped)
    # every regenerated take comes back clean; the shipped audio has a stray
    recog = FakeRecognizer({"shipped.wav": clean + "tʃə"}, clean)
    r = fix_pass._best_tail_take(chunk, {"phones": "tʃə", "length": 3},
                                 _args(), FakeTTS(tmp_path), recog)
    assert r["kept"] is True
    assert r["after_len"] == 0


@espeak
def test_take_that_only_shortens_the_stray_is_still_kept(tmp_path):
    clean = clean_ipa(g2p(TEXT))
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"")
    chunk = FakeChunk(1, TEXT, shipped)
    recog = FakeRecognizer({"shipped.wav": clean + "tʃə"}, clean + "t")
    r = fix_pass._best_tail_take(chunk, {"phones": "tʃə", "length": 3},
                                 _args(), FakeTTS(tmp_path), recog)
    assert r["kept"] is True
    assert r["after_len"] == 1


@espeak
def test_no_improvement_is_discarded(tmp_path):
    """Never ship a swap that did not beat what is already on disk."""
    clean = clean_ipa(g2p(TEXT))
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"")
    chunk = FakeChunk(1, TEXT, shipped)
    recog = FakeRecognizer({"shipped.wav": clean + "tʃə"}, clean + "tʃə")
    r = fix_pass._best_tail_take(chunk, {"phones": "tʃə", "length": 3},
                                 _args(), FakeTTS(tmp_path), recog)
    assert r["kept"] is False


@espeak
def test_take_that_clears_the_tail_but_breaks_a_word_is_rejected(tmp_path):
    """The accept test is asymmetric: a clean tail does not buy a mangled word."""
    clean = clean_ipa(g2p(TEXT))
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"")
    chunk = FakeChunk(1, TEXT, shipped)
    # regenerated audio has no trailing stray, but "need" is replaced by garbage
    broken = clean.replace(clean_ipa(g2p("need")), "zzzzxq")
    recog = FakeRecognizer({"shipped.wav": clean + "tʃə"}, broken)
    r = fix_pass._best_tail_take(chunk, {"phones": "tʃə", "length": 3},
                                 _args(), FakeTTS(tmp_path), recog)
    assert r["kept"] is False
    assert r["broke_words"], "a newly mispronounced word must be reported"


@espeak
def test_every_param_take_is_tried(tmp_path):
    clean = clean_ipa(g2p(TEXT))
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"")
    chunk = FakeChunk(1, TEXT, shipped)
    tts = FakeTTS(tmp_path)
    recog = FakeRecognizer({"shipped.wav": clean + "tʃə"}, clean)
    fix_pass._best_tail_take(chunk, {"phones": "tʃə", "length": 3}, _args(3), tts, recog)
    assert len(tts.calls) == 3
    assert {"temperature": 0.85} in tts.calls


@espeak
def test_apply_replaces_the_chunk_wav_atomically(tmp_path):
    """--apply swaps the winning take over the shipped wav; concatenation is keyed
    on chunk mtimes, so nothing else needs updating for a re-export to pick it up."""
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"OLD")
    winner = tmp_path / "winner.wav"
    winner.write_bytes(b"NEW")
    chunk = FakeChunk(1, TEXT, shipped)

    fix_pass._apply_take(chunk, {"wav": str(winner)})

    assert shipped.read_bytes() == b"NEW"
    assert not list(tmp_path.glob("*.tmp")), "temp file must not survive"
