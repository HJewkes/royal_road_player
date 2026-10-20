"""VllmBatchRenderer and the stock retake pass against a fake chatterbox-vllm.

The fake interpreter runs a copy of the real batch worker with stub
`chatterbox_vllm` and `perth` packages first on its path and a stub
`s3gen_batch.py` beside it. The stub model logs what it was built and called with
(pid, cwd, CHATTERBOX_CFG_SCALE, kwargs) and hands its S3Gen one sample-long
"token" per output sample; the stub BatchedS3Gen turns those into a sine. The
length follows the text at a natural pace, unless the text asks to be cut short.
A text saying "crash here" fails its batch; one saying "die here" kills the worker.
"""

import json
import os
import shutil
import signal
import stat
import sys
import time
import wave
from pathlib import Path

import pytest

from src.config import get_settings
from src.tts.batch import WORKER, VllmBatchRenderer, render_chapter_batched
from src.tts.early_stop import spoken_letters, take_shortfall
from src.tts.profiles import T1

SAMPLE_RATE = 24000
NATURAL_LETTERS_PER_S = 14.0

FAKE_PYTHON = '''#!{python}
import runpy, sys
sys.path[:0] = {stubs!r}
worker = {worker!r}
sys.argv = [worker] + sys.argv[3:]
runpy.run_path(worker, run_name="__main__")
'''

STUB_TTS = '''
import json, os
import numpy as np

# vLLM logs to stdout as soon as it is imported.
print("INFO Automatically detected platform cuda.")

LOG = os.environ["FAKE_VLLM_LOG"]


def _log(event):
    with open(LOG, "a") as log:
        log.write(json.dumps(event) + "\\n")


def _seconds(text):
    if "cut short" in text:
        return 1.0
    return sum(ch.isalnum() for ch in text) / {pace}


class PortS3Gen:
    def inference(self, **kwargs):
        raise AssertionError("decoded with the port's one-take-at-a-time S3Gen")


class ChatterboxTTS:
    sr = 24000

    def __init__(self):
        self.s3gen = PortS3Gen()

    @classmethod
    def from_pretrained(cls, **kwargs):
        _log({{"event": "load", "pid": os.getpid(), "cwd": os.getcwd(), "cfg": os.environ.get("CHATTERBOX_CFG_SCALE"), **kwargs}})
        return cls()

    def get_audio_conditionals(self, audio_prompt_path):
        if not isinstance(self.s3gen, PortS3Gen):
            raise AssertionError("the port's S3Gen was not put back")
        return {{"reference": audio_prompt_path}}, "cond_emb"

    def generate_with_conds(self, prompts, s3gen_ref, cond_emb, **kwargs):
        _log({{"event": "generate", "prompts": prompts, **kwargs}})
        if any("crash here" in p for p in prompts):
            raise RuntimeError("CUDA error: out of memory")
        if any("die here" in p for p in prompts):
            os._exit(1)
        for p in prompts:
            tokens = np.zeros(int(self.sr * _seconds(p)))
            self.s3gen.inference(speech_tokens=tokens, ref_dict=s3gen_ref, n_timesteps=kwargs["diffusion_steps"])
        return []

    def shutdown(self):
        _log({{"event": "shutdown", "pid": os.getpid()}})
'''

STUB_PERTH = '''
import json, os


class PerthImplicitWatermarker:
    def apply_watermark(self, wav, sample_rate):
        with open(os.environ["FAKE_VLLM_LOG"], "a") as log:
            log.write(json.dumps({"event": "watermark", "samples": len(wav), "sample_rate": sample_rate}) + "\\n")
        return wav
'''

STUB_S3GEN_BATCH = '''
import json, os
import numpy as np


class BatchedS3Gen:
    def __init__(self, s3gen, max_padded_tokens, flow_dtype=None):
        pass

    def wavs(self, token_seqs, ref, n_timesteps):
        with open(os.environ["FAKE_VLLM_LOG"], "a") as log:
            log.write(json.dumps({"event": "s3gen", "takes": len(token_seqs), "ref": ref, "n_timesteps": n_timesteps}) + "\\n")
        return [(0.1 * np.sin(2 * np.pi * 220 * np.arange(len(t)) / 24000))[None, :] for t in token_seqs]
'''

CHUNKS = [
    (4, "The lantern swung above the quiet harbour while the gulls circled overhead."),
    (5, "Nobody spoke."),
    (6, "Mara counted the crates twice, then a third time, because the ledger never matched the hold."),
]


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def vllm(tmp_path, monkeypatch):
    """A configured renderer factory, vllm(watermark=..., tempo=..., perth=...); closes them all after."""
    clone = tmp_path / "clone"
    clone.mkdir()
    log = tmp_path / "vllm.log"
    monkeypatch.setenv("FAKE_VLLM_LOG", str(log))
    _write(tmp_path / "stubs" / "model" / "chatterbox_vllm" / "__init__.py", "")
    _write(tmp_path / "stubs" / "model" / "chatterbox_vllm" / "tts.py", STUB_TTS.format(pace=NATURAL_LETTERS_PER_S))
    _write(tmp_path / "stubs" / "perth" / "perth" / "__init__.py", STUB_PERTH)
    reference = _write(tmp_path / "reference.wav", "wav")
    worker = tmp_path / "worker" / WORKER.name
    worker.parent.mkdir()
    shutil.copy(WORKER, worker)
    shutil.copy(WORKER.with_name("chatterbox_audio.py"), worker.parent)
    _write(worker.with_name("s3gen_batch.py"), STUB_S3GEN_BATCH)

    def make(perth: bool = True, **overrides):
        stubs = [str(tmp_path / "stubs" / "model")] + ([str(tmp_path / "stubs" / "perth")] if perth else [])
        python = _write(tmp_path / f"fake-python-{len(stubs)}", FAKE_PYTHON.format(python=sys.executable, stubs=stubs, worker=str(worker)))
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
        settings = get_settings().model_copy(update={
            "chatterbox_vllm_python": str(python), "chatterbox_vllm_dir": str(clone),
            "chatterbox_vllm_tempo": 1.0, "chatterbox_vllm_timeout_s": 60.0, **overrides,
        })
        renderers.append(VllmBatchRenderer(settings=settings, reference=str(reference)))
        return renderers[-1]

    renderers: list[VllmBatchRenderer] = []
    make.log = lambda: [json.loads(line) for line in log.read_text().splitlines()]
    make.loads = lambda: [event for event in make.log() if event["event"] == "load"]
    make.clone = clone
    yield make
    for renderer in renderers:
        renderer.close()


class FakeStock:
    """Stands in for the stock Chatterbox engine: writes a full-length take and records the call."""

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def synthesize(self, text, output_path, seed=None, **kwargs):
        self.calls.append((text, seed))
        seconds = spoken_letters(text) / NATURAL_LETTERS_PER_S + T1.trailing_pad_s
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(bytes(2 * int(SAMPLE_RATE * seconds)))
        return Path(output_path), 0.1


def _seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def test_results_map_back_to_chunk_indices_in_order(vllm, tmp_path):
    takes = vllm().render_chapter(CHUNKS, tmp_path / "chunks")

    assert [take.index for take in takes] == [4, 5, 6]
    assert all(take.ok and take.path.name == f"{take.index:03d}.wav" for take in takes)
    for (_, text), take in zip(CHUNKS, takes):
        expected = spoken_letters(text) / NATURAL_LETTERS_PER_S + T1.trailing_pad_s
        assert _seconds(take.path) == pytest.approx(expected, abs=0.01)


def test_cfg_reaches_worker_via_env(vllm, tmp_path):
    vllm(chatterbox_vllm_cfg=0.7).render_chapter(CHUNKS, tmp_path / "chunks")

    load = vllm.log()[0]
    assert load["event"] == "load" and load["cfg"] == "0.7"
    assert all("cfg" not in event and "cfg_weight" not in event for event in vllm.log()[1:])


def test_top_p_and_repetition_penalty_are_explicit(vllm, tmp_path):
    vllm().render_chapter(CHUNKS, tmp_path / "chunks")

    generate = next(event for event in vllm.log() if event["event"] == "generate")
    assert (generate["top_p"], generate["repetition_penalty"]) == (1.0, 1.2)
    assert (generate["temperature"], generate["min_p"], generate["exaggeration"]) == (0.8, 0.05, 0.5)
    assert generate["diffusion_steps"] == 10


def test_worker_runs_with_cwd_at_the_clone(vllm, tmp_path):
    vllm().render_chapter(CHUNKS, tmp_path / "chunks")

    assert Path(vllm.log()[0]["cwd"]) == vllm.clone


def test_chapter_renders_in_batches_of_max_batch(vllm, tmp_path):
    vllm(chatterbox_vllm_max_batch=2).render_chapter(CHUNKS, tmp_path / "chunks")

    load, *generates = vllm.log()
    assert (load["max_batch_size"], load["max_num_seqs"]) == (2, 2)
    assert [len(event["prompts"]) for event in generates if event["event"] == "generate"] == [2, 1]


def test_t3_tokens_decode_through_batched_s3gen_with_the_reference(vllm, tmp_path):
    vllm(chatterbox_vllm_max_batch=2).render_chapter(CHUNKS, tmp_path / "chunks")

    decodes = [event for event in vllm.log() if event["event"] == "s3gen"]
    assert [event["takes"] for event in decodes] == [2, 1]
    assert all(event["n_timesteps"] == 10 for event in decodes)
    assert all(Path(event["ref"]["reference"]).name == "reference.wav" for event in decodes)


def test_every_vllm_take_is_watermarked(vllm, tmp_path):
    vllm().render_chapter(CHUNKS, tmp_path / "chunks")

    assert sum(event["event"] == "watermark" for event in vllm.log()) == len(CHUNKS)


def test_missing_perth_fails_the_batch_instead_of_skipping_the_watermark(vllm, tmp_path):
    stock = FakeStock()

    report = render_chapter_batched(CHUNKS, tmp_path / "chunks", vllm(perth=False), lambda: stock)

    assert "chatterbox-vllm worker failed" in report.batch_failed
    assert report.retakes["failed"] == [4, 5, 6]
    assert [text for text, _ in stock.calls] == [text for _, text in CHUNKS]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_tempo_speeds_up_the_take_before_the_pad(vllm, tmp_path):
    takes = vllm(chatterbox_vllm_tempo=1.25).render_chapter(CHUNKS[:1], tmp_path / "chunks")

    speech_s = spoken_letters(CHUNKS[0][1]) / NATURAL_LETTERS_PER_S
    assert _seconds(takes[0].path) == pytest.approx(speech_s / 1.25 + T1.trailing_pad_s, abs=0.05)


def test_flagged_takes_rerender_on_stock_engine(vllm, tmp_path):
    chunks = CHUNKS + [(7, "The ferry left at noon and nobody aboard looked back at the town, cut short.")]
    stock = FakeStock()

    report = render_chapter_batched(chunks, tmp_path / "chunks", vllm(), lambda: stock, seed_for=lambda i: 999 + i)

    assert report.retakes == {"early_stop": [7], "hallucination": [], "failed": []}
    assert stock.calls == [(chunks[3][1], 1006)]
    assert _seconds(tmp_path / "chunks" / "007.wav") > 4.0


def test_vllm_failure_falls_back_to_stock(vllm, tmp_path):
    chunks = CHUNKS + [(7, "The storm came in sideways and the crash here was only the shutters.")]
    stock = FakeStock()

    report = render_chapter_batched(chunks, tmp_path / "chunks", vllm(chatterbox_vllm_max_batch=2), lambda: stock)

    assert report.batch_failed is not None
    assert report.retakes["failed"] == [6, 7]
    assert [text for text, _ in stock.calls] == [chunks[2][1], chunks[3][1]]
    assert all((tmp_path / "chunks" / f"{index:03d}.wav").exists() for index, _ in chunks)


CHAPTER_TWO = [
    (0, "The tide turned before dawn and the harbour emptied of everything but rope."),
    (1, "Mara closed the ledger."),
]


def _wait_for_exit(renderer: VllmBatchRenderer, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while renderer._process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)


def test_one_worker_serves_consecutive_chapters(vllm, tmp_path):
    """Catches spawning (or closing) the worker per chapter: the model would load twice."""
    renderer = vllm()

    first = renderer.render_chapter(CHUNKS, tmp_path / "ch1")
    second = renderer.render_chapter(CHAPTER_TWO, tmp_path / "ch2")

    assert len(vllm.loads()) == 1
    assert all(take.ok and take.path.exists() for take in first + second)
    assert [event["prompts"] for event in vllm.log() if event["event"] == "generate"] == [
        [text for _, text in CHUNKS], [text for _, text in CHAPTER_TWO]
    ]


def test_worker_that_died_between_chapters_is_respawned(vllm, tmp_path):
    """Catches dropping the respawn-and-resend for a reused worker that has exited:
    the chapter would fail and go to stock."""
    renderer = vllm()
    renderer.render_chapter(CHUNKS, tmp_path / "ch1")
    os.kill(vllm.loads()[0]["pid"], signal.SIGKILL)
    _wait_for_exit(renderer)

    takes = renderer.render_chapter(CHAPTER_TWO, tmp_path / "ch2")

    assert all(take.ok for take in takes)
    assert len({event["pid"] for event in vllm.loads()}) == 2


def test_idle_worker_exits_and_the_next_chapter_respawns_it(vllm, tmp_path):
    """Catches a worker that waits for requests with no idle timeout: it would hold the GPU forever."""
    renderer = vllm(chatterbox_vllm_idle_timeout_s=0.5)
    renderer.render_chapter(CHUNKS, tmp_path / "ch1")

    _wait_for_exit(renderer)

    assert renderer._process.poll() == 0
    assert [event["event"] for event in vllm.log()][-1] == "shutdown"
    assert all(take.ok for take in renderer.render_chapter(CHAPTER_TWO, tmp_path / "ch2"))
    assert len(vllm.loads()) == 2


def test_cfg_change_respawns_the_worker(vllm, tmp_path):
    """Catches reusing the warm worker across a CFG change: the port reads CFG once per process."""
    renderer = vllm(chatterbox_vllm_cfg=0.5)
    renderer.render_chapter(CHUNKS, tmp_path / "ch1")
    renderer.settings = renderer.settings.model_copy(update={"chatterbox_vllm_cfg": 0.7})

    renderer.render_chapter(CHAPTER_TWO, tmp_path / "ch2")

    assert [event["cfg"] for event in vllm.loads()] == ["0.5", "0.7"]


def test_worker_death_mid_chapter_keeps_finished_takes(vllm, tmp_path):
    """Catches dropping the takes a worker finished before it died: they would all re-render on stock."""
    chunks = CHUNKS + [(7, "The storm came in sideways and the die here was only the shutters.")]
    renderer = vllm(chatterbox_vllm_max_batch=2)
    stock = FakeStock()

    report = render_chapter_batched(chunks, tmp_path / "chunks", renderer, lambda: stock)

    assert "worker exited" in report.batch_failed
    assert report.retakes["failed"] == [6, 7]
    assert [text for text, _ in stock.calls] == [chunks[2][1], chunks[3][1]]
    assert all(take.ok for take in renderer.render_chapter(CHAPTER_TWO, tmp_path / "ch2"))
    assert len(vllm.loads()) == 2


def test_unconfigured_vllm_renders_the_chapter_on_stock(tmp_path):
    settings = get_settings().model_copy(update={"chatterbox_vllm_python": ""})
    stock = FakeStock()

    report = render_chapter_batched(CHUNKS, tmp_path / "chunks", VllmBatchRenderer(settings=settings), lambda: stock)

    assert "AUDIOBOOK_CHATTERBOX_VLLM_PYTHON" in report.batch_failed
    assert len(stock.calls) == len(CHUNKS)


class FakeRecognizer:
    """Hears babble in the takes it is told to and records every batch it is handed.

    batch.load_slice is patched to hand over the take's path, so a "sample array" here is a path.
    """

    def __init__(self, babbled: set[int]):
        self.babbled = babbled
        self.batches: list[list[int]] = []

    def recognize(self, path) -> str:
        stem = Path(path).stem
        return "babble" if stem.isdigit() and int(stem) in self.babbled else "clean"

    def recognize_batch(self, paths) -> list[str]:
        self.batches.append([int(Path(path).stem) for path in paths])
        return [self.recognize(path) for path in paths]


@pytest.fixture
def heard(monkeypatch):
    """Route takes to a FakeRecognizer by path, with babble flagged wherever it hears it.

    Stock retakes, which land in temp files, always read back clean.
    """
    for module in ("src.tts.batch", "src.tts.verified"):
        monkeypatch.setattr(f"{module}.load_slice", lambda path, start, end: path)
        monkeypatch.setattr(f"{module}.detect_hallucinations",
                            lambda text, phones, **kwargs: ["babble"] if phones == "babble" else [])
    return FakeRecognizer


def _per_take_reasons(takes, texts, recognizer):
    """The pre-batching rule: each take checked alone, failed then early_stop then babble."""
    reasons = {}
    for take in takes:
        if not take.ok or not take.path.exists():
            reasons[take.index] = "failed"
        elif take_shortfall(texts[take.index], take.path, T1) is not None:
            reasons[take.index] = "early_stop"
        elif recognizer.recognize(take.path) == "babble":
            reasons[take.index] = "hallucination"
    return reasons


# The early-stop take sits mid-chapter, so the takes the recognizer hears are not a prefix of the chapter.
CUT_SHORT_MIDWAY = [
    CHUNKS[0],
    (5, "The ferry left at noon and nobody aboard looked back at the town, cut short."),
    CHUNKS[2],
    (7, "The storm came in sideways and only the shutters rattled through the night."),
]


def test_batched_verdicts_match_the_per_take_rule(vllm, tmp_path, heard):
    """Catches a babbled early-stop take being filed as a hallucination (checks reordered),
    zipping the recognized subset back against every take, and retaking out of chunk order."""
    recognizer = heard(babbled={4, 5, 7})
    takes = vllm().render_chapter(CUT_SHORT_MIDWAY, tmp_path / "reference")
    stock = FakeStock()

    report = render_chapter_batched(CUT_SHORT_MIDWAY, tmp_path / "chunks", vllm(), lambda: stock, recognizer=recognizer)

    expected = _per_take_reasons(takes, dict(CUT_SHORT_MIDWAY), recognizer)
    assert {index: reason for reason, indices in report.retakes.items() for index in indices} == expected
    assert report.retakes == {"early_stop": [5], "hallucination": [4, 7], "failed": []}
    assert [text for text, _ in stock.calls] == [CUT_SHORT_MIDWAY[i][1] for i in (0, 1, 3)]


def test_takes_reach_the_recognizer_in_one_batch_in_take_order(vllm, tmp_path, heard):
    """Catches recognizing takes one call at a time, and sending a take that already
    failed its early-stop check to the recognizer."""
    recognizer = heard(babbled=set())

    render_chapter_batched(CUT_SHORT_MIDWAY, tmp_path / "chunks", vllm(), FakeStock, recognizer=recognizer)

    assert recognizer.batches == [[4, 6, 7]]


def test_failed_takes_never_reach_the_recognizer(vllm, tmp_path, heard):
    """Catches sending a take the batch never wrote to the recognizer."""
    chunks = CHUNKS + [(7, "The storm came in sideways and the crash here was only the shutters.")]
    recognizer = heard(babbled={4})

    report = render_chapter_batched(chunks, tmp_path / "chunks", vllm(chatterbox_vllm_max_batch=2), FakeStock,
                                    recognizer=recognizer)

    assert recognizer.batches == [[4, 5]]
    assert report.retakes == {"early_stop": [], "hallucination": [4], "failed": [6, 7]}
