"""Batch rendering: a whole chapter through one worker run, with retakes on stock.

A BatchRenderer takes a chapter's (index, text) chunks and returns a TakeResult
per chunk, in chunk order. VllmBatchRenderer fills it with chatterbox-vllm,
which runs under its own venv (torch 2.7.1, vLLM 0.10.0) and so, like stock
Chatterbox, sits behind a process boundary: a worker that stays loaded across
chapters, a chapter's request line in, a reply line per take out.

render_chapter_batched then checks every take with the early-stop guard (the
vLLM profile's own threshold) and the hallucination detector, and sends the
flagged ones, plus any the batch failed, back to the same warm worker as one
mini-batch with a fresh seed each, for up to chatterbox_vllm_retake_rounds
rounds. Whatever is still flagged after that re-renders on the stock engine
through synthesize_verified. If the batch worker cannot run at all, the whole
chapter renders on stock; if it dies during a retake round, the chunks that
round did not finish go to stock.
"""

import json
import logging
import os
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Optional, Protocol

from src.config import get_settings
from src.tts.chatterbox import pump_lines
from src.tts.early_stop import take_shortfall
from src.tts.profiles import T1, VllmProfile
from src.tts.verified import SEED_STRIDE, synthesize_verified
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

    def render_chapter(
        self, chunks: list[tuple[int, str]], out_dir: Path, seeds: Optional[dict[int, int]] = None
    ) -> list[TakeResult]: ...


class _WorkerError(RuntimeError):
    pass


class _WorkerExited(_WorkerError):
    pass


class VllmBatchRenderer:
    """Renders chapters on one warm chatterbox-vllm worker, max_batch chunks at a time.

    The worker loads the model once and serves chapter after chapter over a pipe
    until it has sat idle for chatterbox_vllm_idle_timeout_s. CFG is process-global
    in the port, so a change to it, or to anything else the worker loads with,
    respawns the worker. close() frees the GPU at once.
    """

    def __init__(self, settings=None, profile: VllmProfile = T1, reference: Optional[str] = None):
        self.settings = settings or get_settings()
        self.profile = profile
        self.reference = reference or self.settings.chatterbox_reference_path
        self._process: Optional[subprocess.Popen] = None
        self._spawned_with: Optional[tuple] = None
        self._replies: queue.Queue = queue.Queue()

    def render_chapter(
        self, chunks: list[tuple[int, str]], out_dir: Path, seeds: Optional[dict[int, int]] = None
    ) -> list[TakeResult]:
        """Render chunks to out_dir/NNN.wav; a chunk in seeds samples with that seed, the rest unseeded."""
        self._check_runnable()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {index: (out_dir / f"{index:03d}.wav").resolve() for index, _ in chunks}
        replies: dict[int, dict] = {}
        failure = self._render(self._request(chunks, paths, seeds or {}), replies)
        takes = [_take(index, paths[index], replies.get(index)) for index, _ in chunks]
        if failure:
            raise BatchRenderError(failure, takes)
        return takes

    def close(self) -> None:
        process, self._process, self._spawned_with = self._process, None, None
        if process is None or process.poll() is not None:
            return
        process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _request(self, chunks: list[tuple[int, str]], paths: dict[int, Path], seeds: dict[int, int]) -> dict:
        s, p = self.settings, self.profile
        return {
            "reference": str(Path(self.reference).resolve()),
            "sampling": p.sampling_kwargs(),
            "diffusion_steps": s.chatterbox_vllm_diffusion_steps,
            "tempo": s.chatterbox_vllm_tempo,
            "target_lufs": p.target_lufs,
            "trailing_pad_s": p.trailing_pad_s,
            "items": [_item(index, text, paths[index], seeds.get(index)) for index, text in chunks],
        }

    def _render(self, request: dict, replies: dict[int, dict]) -> Optional[str]:
        """Run the chapter on the warm worker, filling replies by index; the failure, if it had one."""
        try:
            reused = self._ensure_worker()
            try:
                self._exchange(request, replies)
            except _WorkerExited:
                # A reused worker may have idled out or died since the last chapter.
                if not reused or replies:
                    raise
                logger.warning("chatterbox-vllm worker had exited; respawning it for this chapter")
                self.close()
                self._ensure_worker()
                self._exchange(request, replies)
        except (OSError, _WorkerError) as exc:
            self.close()
            return f"chatterbox-vllm worker failed: {exc}"
        return None

    def _ensure_worker(self) -> bool:
        """Spawn a worker unless one with these settings is up; whether one was reused."""
        key = self._spawn_key()
        if self._process is not None and self._spawned_with == key:
            return True
        self.close()
        self._spawn(key)
        ready = self._read_reply(time.monotonic() + self.settings.chatterbox_vllm_timeout_s)
        if not ready.get("ready"):
            raise _WorkerError(f"worker did not start: {ready}")
        logger.info(f"chatterbox-vllm worker ready (pid {self._process.pid})")
        return False

    def _spawn_key(self) -> tuple:
        s = self.settings
        return (s.chatterbox_vllm_python, s.chatterbox_vllm_dir, s.chatterbox_vllm_cfg,
                s.chatterbox_vllm_max_batch, s.chatterbox_vllm_watermark, s.chatterbox_vllm_idle_timeout_s)

    def _spawn(self, key: tuple) -> None:
        s = self.settings
        # The port reads CFG from the environment once per process; a kwarg is ignored.
        env = {**os.environ, "CHATTERBOX_CFG_SCALE": str(s.chatterbox_vllm_cfg)}
        command = [
            s.chatterbox_vllm_python, "-I", str(WORKER), "--max-batch", str(s.chatterbox_vllm_max_batch),
            "--idle-timeout", str(s.chatterbox_vllm_idle_timeout_s),
        ] + ([] if s.chatterbox_vllm_watermark else ["--no-watermark"])
        self._process = subprocess.Popen(
            command, cwd=s.chatterbox_vllm_dir, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self._spawned_with, self._replies = key, queue.Queue()
        threading.Thread(target=pump_lines, args=(self._process.stdout, self._replies), daemon=True).start()

    def _exchange(self, request: dict, replies: dict[int, dict]) -> None:
        deadline = time.monotonic() + self.settings.chatterbox_vllm_timeout_s
        try:
            self._process.stdin.write(json.dumps(request) + "\n")
            self._process.stdin.flush()
        except OSError as exc:  # BrokenPipeError: it exited since the last chapter
            raise _WorkerExited("worker pipe closed") from exc
        while True:
            reply = self._read_reply(deadline)
            if "index" in reply:
                replies[int(reply["index"])] = reply
            elif reply.get("done"):
                if reply.get("error"):
                    raise _WorkerError(reply["error"])
                return
            else:
                raise _WorkerError(f"worker broke the protocol: {reply}")

    def _read_reply(self, deadline: float) -> dict:
        try:
            line = self._replies.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            self._process.kill()
            raise _WorkerError(f"worker gave no reply in {self.settings.chatterbox_vllm_timeout_s:.0f}s") from None
        if line is None:
            raise _WorkerExited("worker exited")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise _WorkerError(f"worker broke the protocol: {line[:200]!r}") from exc

    def _check_runnable(self) -> None:
        s = self.settings
        if not s.chatterbox_vllm_python or not Path(s.chatterbox_vllm_python).is_file():
            raise VllmUnavailable("set AUDIOBOOK_CHATTERBOX_VLLM_PYTHON (make setup-chatterbox-vllm)")
        if not s.chatterbox_vllm_dir or not Path(s.chatterbox_vllm_dir).is_dir():
            raise VllmUnavailable("set AUDIOBOOK_CHATTERBOX_VLLM_DIR to the chatterbox-vllm clone")


def _item(index: int, text: str, out: Path, seed: Optional[int]) -> dict:
    item = {"index": index, "text": text, "out": str(out)}
    return item if seed is None else {**item, "seed": seed}


def _take(index: int, path: Path, reply: Optional[dict]) -> TakeResult:
    if reply is None:
        return TakeResult(index, path, ok=False, error="no result from the batch worker")
    return TakeResult(index, path, ok=bool(reply.get("ok")), audio_s=reply.get("audio_s"), error=reply.get("error"))


Flags = dict[str, list[int]]


def _no_flags() -> Flags:
    return {"early_stop": [], "hallucination": [], "failed": []}


@dataclass
class BatchReport:
    """What a chapter's batch render did.

    rounds[0] holds the takes the batch flagged and rounds[n] those still flagged
    after vLLM retake round n; retakes holds the ones that went on to stock, by
    the reason their last vLLM take was flagged for.
    """

    batch_s: float = 0.0
    vllm_retake_s: float = 0.0
    retake_s: float = 0.0
    batch_failed: Optional[str] = None
    retake_failed: Optional[str] = None
    rounds: list[Flags] = field(default_factory=list)
    retakes: Flags = field(default_factory=_no_flags)

    @property
    def retake_count(self) -> int:
        return _count(self.retakes)

    @property
    def round_counts(self) -> list[int]:
        return [_count(flags) for flags in self.rounds]


def _count(flags: Flags) -> int:
    return sum(len(indices) for indices in flags.values())


def render_chapter_batched(
    chunks: list[tuple[int, str]],
    out_dir: Path,
    renderer: BatchRenderer,
    stock_factory: Callable[[], object],
    recognizer=None,
    seed_for: Callable[[int], int] = lambda index: index,
    retake_rounds: Optional[int] = None,
) -> BatchReport:
    """Render every chunk to out_dir/NNN.wav: the batch, vLLM retake rounds, then stock for what is left."""
    report = BatchReport()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = dict(chunks)
    check = partial(_flags, texts, renderer.profile, recognizer)

    began = time.perf_counter()
    takes, report.batch_failed = _render_or_fail(renderer, chunks, out_dir)
    report.batch_s = time.perf_counter() - began
    if report.batch_failed:
        logger.error(f"Batch render failed; its unfinished chunks render on stock Chatterbox: {report.batch_failed}")
    report.rounds.append(check(takes))

    if not report.batch_failed:
        rounds = get_settings().chatterbox_vllm_retake_rounds if retake_rounds is None else retake_rounds
        _retake_in_vllm(report, renderer, texts, out_dir, check, seed_for, rounds)
    report.retakes = report.rounds[-1]
    _retake_on_stock(report, texts, out_dir, stock_factory, recognizer, seed_for)
    return report


def _render_or_fail(renderer: BatchRenderer, chunks, out_dir: Path, seeds=None) -> tuple[list[TakeResult], Optional[str]]:
    """The renderer's takes, and its failure if it had one; takes it never finished come back failed."""
    try:
        return renderer.render_chapter(chunks, out_dir, seeds), None
    except (VllmUnavailable, BatchRenderError) as exc:
        takes = getattr(exc, "takes", None) or [
            TakeResult(index, out_dir / f"{index:03d}.wav", ok=False, error=str(exc)) for index, _ in chunks
        ]
        return takes, str(exc)


def _retake_in_vllm(report: BatchReport, renderer, texts: dict, out_dir: Path, check, seed_for, rounds: int) -> None:
    """Re-render the flagged takes on the warm worker, all of a round in one request, a fresh seed each."""
    began = time.perf_counter()
    for round_number in range(1, rounds + 1):
        still_flagged = {index for indices in report.rounds[-1].values() for index in indices}
        flagged = [index for index in texts if index in still_flagged]
        if not flagged:
            break
        logger.info(f"vLLM retake round {round_number}: {report.rounds[-1]}")
        seeds = {index: seed_for(index) + round_number * SEED_STRIDE for index in flagged}
        takes, report.retake_failed = _render_or_fail(renderer, [(index, texts[index]) for index in flagged], out_dir, seeds)
        report.rounds.append(check(takes))
        if report.retake_failed:
            logger.error(f"vLLM retake round {round_number} failed; its unfinished chunks go to stock: {report.retake_failed}")
            break
    report.vllm_retake_s = time.perf_counter() - began


def _flags(texts: dict, profile: VllmProfile, recognizer, takes: list[TakeResult]) -> Flags:
    """Each take that needs a retake, filed under its reason, in take order."""
    flags = _no_flags()
    for take, reason in zip(takes, _retake_reasons(takes, texts, profile, recognizer)):
        if reason:
            flags[reason].append(take.index)
    return flags


def _retake_reasons(takes: list[TakeResult], texts: dict, profile: VllmProfile, recognizer) -> list[Optional[str]]:
    """Each take's retake reason, in take order: failed, then early_stop, then hallucination.

    Only the takes that pass the first two checks reach the recognizer, and they
    go to it together so it can batch them.
    """
    reasons = [_render_fault(take, texts[take.index], profile) for take in takes]
    heard = [take for take, reason in zip(takes, reasons) if reason is None]
    if recognizer is None or not heard:
        return reasons
    phones = recognizer.recognize_batch([load_slice(take.path, None, None) for take in heard])
    babbled = {take.index for take, take_phones in zip(heard, phones) if detect_hallucinations(texts[take.index], take_phones)}
    return ["hallucination" if take.index in babbled else reason for take, reason in zip(takes, reasons)]


def _render_fault(take: TakeResult, text: str, profile: VllmProfile) -> Optional[str]:
    if not take.ok or not take.path.exists():
        return "failed"
    if take_shortfall(text, take.path, profile) is not None:
        return "early_stop"
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
