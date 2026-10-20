"""Batch rendering: a whole chapter through one worker run, with retakes on stock.

A BatchRenderer takes a chapter's (index, text) chunks and returns a TakeResult
per chunk, in chunk order. VllmBatchRenderer fills it with chatterbox-vllm,
which runs under its own venv (torch 2.7.1, vLLM 0.10.0) and so, like stock
Chatterbox, sits behind a process boundary: a request JSON in, a results JSONL
out.

render_chapter_batched then checks every take with the early-stop guard (the
vLLM profile's own threshold) and the hallucination detector, and re-renders
the flagged ones, plus any the batch failed, on the stock engine through
synthesize_verified. If the batch worker cannot run at all, the whole chapter
renders on stock.
"""

import json
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from src.config import get_settings
from src.tts.early_stop import take_shortfall
from src.tts.profiles import T1, VllmProfile
from src.tts.verified import synthesize_verified
from src.validation.phonemes import detect_hallucinations, load_slice

logger = logging.getLogger(__name__)

WORKER = Path(__file__).with_name("chatterbox_vllm_worker.py")


class VllmUnavailable(RuntimeError):
    """No chatterbox-vllm interpreter or clone configured on this host."""


class BatchRenderError(RuntimeError):
    """The batch worker failed; `takes` holds what it finished before it did."""

    def __init__(self, message: str, takes: Optional[list["TakeResult"]] = None):
        super().__init__(message)
        self.takes = takes


@dataclass
class TakeResult:
    index: int
    path: Path
    ok: bool
    audio_s: Optional[float] = None
    error: Optional[str] = None


class BatchRenderer(Protocol):
    profile: VllmProfile

    def render_chapter(self, chunks: list[tuple[int, str]], out_dir: Path) -> list[TakeResult]: ...


class VllmBatchRenderer:
    """Renders a chapter in one chatterbox-vllm worker run, max_batch chunks at a time."""

    def __init__(self, settings=None, profile: VllmProfile = T1, reference: Optional[str] = None):
        self.settings = settings or get_settings()
        self.profile = profile
        self.reference = reference or self.settings.chatterbox_reference_path

    def render_chapter(self, chunks: list[tuple[int, str]], out_dir: Path) -> list[TakeResult]:
        self._check_runnable()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {index: (out_dir / f"{index:03d}.wav").resolve() for index, _ in chunks}
        with tempfile.TemporaryDirectory(prefix="vllm-batch-") as scratch:
            request_path, results_path = Path(scratch) / "request.json", Path(scratch) / "results.jsonl"
            request_path.write_text(json.dumps(self._request(chunks, paths)), encoding="utf-8")
            failure = self._run(request_path, results_path)
            replies = _read_results(results_path)
        takes = [_take(index, paths[index], replies.get(index)) for index, _ in chunks]
        if failure:
            raise BatchRenderError(failure, takes)
        return takes

    def _request(self, chunks: list[tuple[int, str]], paths: dict[int, Path]) -> dict:
        s, p = self.settings, self.profile
        return {
            "reference": str(Path(self.reference).resolve()),
            "sampling": p.sampling_kwargs(),
            "diffusion_steps": s.chatterbox_vllm_diffusion_steps,
            "max_batch": s.chatterbox_vllm_max_batch,
            "tempo": s.chatterbox_vllm_tempo,
            "watermark": s.chatterbox_vllm_watermark,
            "target_lufs": p.target_lufs,
            "trailing_pad_s": p.trailing_pad_s,
            "items": [{"index": index, "text": text, "out": str(paths[index])} for index, text in chunks],
        }

    def _run(self, request_path: Path, results_path: Path) -> Optional[str]:
        """Run the worker; the failure, if it had one."""
        s = self.settings
        # The port reads CFG from the environment once per process; a kwarg is ignored.
        env = {**os.environ, "CHATTERBOX_CFG_SCALE": str(s.chatterbox_vllm_cfg)}
        command = [s.chatterbox_vllm_python, "-I", str(WORKER), str(request_path), str(results_path)]
        try:
            subprocess.run(command, cwd=s.chatterbox_vllm_dir, env=env, check=True, timeout=s.chatterbox_vllm_timeout_s)
        except (OSError, subprocess.SubprocessError) as exc:
            return f"chatterbox-vllm worker failed: {exc}"
        return None

    def _check_runnable(self) -> None:
        s = self.settings
        if not s.chatterbox_vllm_python or not Path(s.chatterbox_vllm_python).is_file():
            raise VllmUnavailable("set AUDIOBOOK_CHATTERBOX_VLLM_PYTHON (make setup-chatterbox-vllm)")
        if not s.chatterbox_vllm_dir or not Path(s.chatterbox_vllm_dir).is_dir():
            raise VllmUnavailable("set AUDIOBOOK_CHATTERBOX_VLLM_DIR to the chatterbox-vllm clone")


def _read_results(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    replies = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {int(reply["index"]): reply for reply in replies}


def _take(index: int, path: Path, reply: Optional[dict]) -> TakeResult:
    if reply is None:
        return TakeResult(index, path, ok=False, error="no result from the batch worker")
    return TakeResult(index, path, ok=bool(reply.get("ok")), audio_s=reply.get("audio_s"), error=reply.get("error"))


@dataclass
class BatchReport:
    batch_s: float = 0.0
    retake_s: float = 0.0
    batch_failed: Optional[str] = None
    retakes: dict[str, list[int]] = field(default_factory=lambda: {"early_stop": [], "hallucination": [], "failed": []})

    @property
    def retake_count(self) -> int:
        return sum(len(indices) for indices in self.retakes.values())


def render_chapter_batched(
    chunks: list[tuple[int, str]],
    out_dir: Path,
    renderer: BatchRenderer,
    stock_factory: Callable[[], object],
    recognizer=None,
    seed_for: Callable[[int], int] = lambda index: index,
) -> BatchReport:
    """Render every chunk to out_dir/NNN.wav: the batch first, then stock for whatever it got wrong."""
    report = BatchReport()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    try:
        takes = renderer.render_chapter(chunks, out_dir)
    except (VllmUnavailable, BatchRenderError) as exc:
        logger.error(f"Batch render failed; its unfinished chunks render on stock Chatterbox: {exc}")
        report.batch_failed = str(exc)
        takes = getattr(exc, "takes", None) or [
            TakeResult(index, out_dir / f"{index:03d}.wav", ok=False, error=str(exc)) for index, _ in chunks
        ]
    report.batch_s = time.perf_counter() - began

    texts = dict(chunks)
    for take in takes:
        reason = _retake_reason(take, texts[take.index], renderer.profile, recognizer)
        if reason:
            report.retakes[reason].append(take.index)
    _retake_on_stock(report, texts, out_dir, stock_factory, recognizer, seed_for)
    return report


def _retake_reason(take: TakeResult, text: str, profile: VllmProfile, recognizer) -> Optional[str]:
    if not take.ok or not take.path.exists():
        return "failed"
    if take_shortfall(text, take.path, profile) is not None:
        return "early_stop"
    if recognizer is not None and detect_hallucinations(text, recognizer.recognize(load_slice(take.path, None, None))):
        return "hallucination"
    return None


def _retake_on_stock(report: BatchReport, texts: dict, out_dir: Path, stock_factory, recognizer, seed_for) -> None:
    indices = sorted(index for group in report.retakes.values() for index in group)
    if not indices:
        return
    logger.warning(f"Re-rendering {len(indices)} batch take(s) on stock Chatterbox: {report.retakes}")
    began = time.perf_counter()
    stock = stock_factory()
    for index in indices:
        out = out_dir / f"{index:03d}.wav"
        if recognizer is not None:
            synthesize_verified(stock, texts[index], out, recognizer=recognizer, seed=seed_for(index))
        else:
            stock.synthesize(texts[index], out, seed=seed_for(index))
    report.retake_s = time.perf_counter() - began
