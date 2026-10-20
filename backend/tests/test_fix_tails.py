"""Tests for the tail-artifact fix path in scripts/fix_pass.py.

No models load: TTS and the phoneme recognizer are stubs, and the "audio" phones
are built from espeak-ng's G2P of the source text so a take can be made clean,
shorter, or word-breaking on demand.
"""
import importlib.util
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.tts.chatterbox import ChatterboxUnavailable
from src.tts.engines import chunk_seed
from src.tts.profiles import P4
from src.tts.verified import SEED_STRIDE
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


def _args(takes=3, engine="xtts"):
    class A:
        pass
    a = A()
    a.takes, a.limit, a.engine = takes, 10, engine
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
def test_already_faulty_word_getting_worse_is_also_a_regression(tmp_path):
    """Set membership could not see this: a word over the fault threshold in BOTH
    renderings never enters or leaves the set, so only distances catch it."""
    shipped = {"need": (0.50, True), "here": (0.10, False)}
    take = {"need": (0.90, True), "here": (0.10, False)}
    assert fix_pass._regressions(shipped, take) == ["need"]


def test_recognizer_noise_below_the_margin_is_not_a_regression():
    shipped = {"need": (0.50, True)}
    take = {"need": (0.50 + fix_pass.WORSE_MARGIN / 2, True)}
    assert fix_pass._regressions(shipped, take) == []


def test_a_word_absent_from_shipped_counts_from_zero():
    assert fix_pass._regressions({}, {"need": (0.9, True)}) == ["need"]


def test_sub_threshold_drift_on_a_healthy_word_is_not_a_regression():
    """Whole-chunk re-synthesis re-renders every word, so distances jitter. Only
    words the take leaves genuinely faulty can disqualify it."""
    shipped = {"across": (0.10, False)}
    take = {"across": (0.40, False)}
    assert fix_pass._regressions(shipped, take) == []


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


@espeak
def test_apply_leaves_no_temp_file_when_the_copy_fails(tmp_path):
    """A raise mid-copy must not strand a .wav.tmp beside the real chunk."""
    shipped = tmp_path / "shipped.wav"
    shipped.write_bytes(b"OLD")
    chunk = FakeChunk(1, TEXT, shipped)

    with pytest.raises(OSError):
        fix_pass._apply_take(chunk, {"wav": str(tmp_path / "does-not-exist.wav")})

    assert shipped.read_bytes() == b"OLD", "the shipped wav must be untouched"
    assert not list(tmp_path.glob("*.tmp"))


def test_write_results_creates_missing_logs_dir(tmp_path):
    out = tmp_path / "logs" / "tail_fix_results.json"

    fix_pass._write_results(out, {"attempted": 0})

    assert out.exists()


# 56 alphanumeric letters, written for this test: a full take needs at least
# 56 / 21.5 = 2.6 s of speech.
LONG_TEXT = "we need to get him here before the storm reaches the harbour"


def _write_wav(path, seconds):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * int(24000 * seconds))
    return path


class FakeWavTTS:
    """Writes a silent wav of a fixed length per take and records its kwargs."""

    def __init__(self, seconds):
        self.calls = []
        self._seconds = seconds

    def synthesize(self, text, out_path, **kw):
        _write_wav(out_path, self._seconds)
        self.calls.append(kw)
        return out_path, 0.0


def _early_stop_fix(tmp_path, take_phones):
    clean = clean_ipa(g2p(LONG_TEXT))
    shipped = _write_wav(tmp_path / "shipped.wav", 1.0 + P4.trailing_pad_s)
    chunk = FakeChunk(1, LONG_TEXT, shipped)
    recog = FakeRecognizer({"shipped.wav": clean}, take_phones(clean))
    before = fix_pass.take_shortfall(LONG_TEXT, shipped, P4)
    assert before is not None, "the shipped take must trip the guard"
    return fix_pass._best_early_stop_take(chunk, before, _args(engine="chatterbox"),
                                          FakeWavTTS(4.0), recog, P4)


@espeak
def test_early_stop_fix_keeps_full_take_without_regressions(tmp_path):
    r = _early_stop_fix(tmp_path, lambda clean: clean)

    assert r["kept"] is True
    assert r["after_shortfall"] == 0


@espeak
def test_early_stop_fix_rejects_full_take_that_breaks_a_word(tmp_path):
    """A complete take does not buy a mangled word, the same rule as the tail pass."""
    r = _early_stop_fix(tmp_path, lambda clean: clean.replace(clean_ipa(g2p("storm")), "zzzzxq"))

    assert r["kept"] is False
    assert r["broke_words"]


class StampDiscovery:
    def __init__(self, engine):
        self._engine = engine

    def read_engine_stamp(self, fiction_id, book, chapter):
        return {"engine": self._engine, "chunking": "any"}


def test_fix_pass_uses_stamp_engine(monkeypatch):
    built = []
    monkeypatch.setattr(fix_pass, "get_tts_engine", lambda name=None: built.append(name) or object())

    name, _ = fix_pass._load_engine(StampDiscovery("chatterbox"), "1", 1, 1)

    assert name == "chatterbox"
    assert built == ["chatterbox"]


def test_fix_pass_refuses_chapter_whose_engine_is_not_runnable(monkeypatch):
    def unavailable(name=None):
        raise ChatterboxUnavailable("no Chatterbox venv")
    monkeypatch.setattr(fix_pass, "get_tts_engine", unavailable)

    with pytest.raises(SystemExit, match="rendered with chatterbox"):
        fix_pass._load_engine(StampDiscovery("chatterbox"), "1", 1, 1)


def test_chatterbox_takes_vary_seed():
    retries = 5  # synthesize_verified's default
    render_seeds = {chunk_seed(7) + n * SEED_STRIDE for n in range(retries + 1)}

    seeds = [params["seed"] for _, params in fix_pass._take_params("chatterbox", 7, 3)]

    assert len(set(seeds)) == 3
    assert not set(seeds) & render_seeds, "a repair must not replay a render-time retake"
