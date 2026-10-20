"""Render chunks in worker processes, each holding its own engine (XTTS by default).

XTTS samples audio tokens one at a time, which spreads poorly across threads: on
the M3 Max, two processes with 5 torch threads each produced 1.57 audio-seconds
per wall-second against 0.83-0.91 for one process using all 10 (2026-09-29).
Separate processes, not threads, because torch's thread count is per process.
A Chatterbox worker drives its own model subprocess (tts/chatterbox.py) and
keeps the phoneme verify loop here.
"""

import logging
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import get_context
from pathlib import Path

logger = logging.getLogger(__name__)

_engine = None
_recognizer = None


def _init_worker(threads: int, workers: int, verify: bool, engine_name: str) -> None:
    """Load a model into this worker and give it its share of the CPU threads."""
    global _engine, _recognizer
    import torch

    from src.tts.engines import get_tts_engine
    from src.validation.phonemes import get_phoneme_recognizer

    torch.set_num_threads(threads or max(1, torch.get_num_threads() // workers))
    _engine = get_tts_engine(engine_name)
    _engine.load_model()
    if verify:
        try:
            _recognizer = get_phoneme_recognizer()
        except Exception as exc:  # noqa: BLE001 - any load failure degrades to single takes
            logger.warning(f"Self-healing synthesis disabled in worker: {exc}")


def _render(text: str, output_path: str, retries: int, seed: int | None) -> tuple[Path, float]:
    """Synthesize one chunk in a worker, self-healing hallucinated or truncated takes."""
    from src.tts.verified import synthesize_verified

    if _recognizer is not None:
        return synthesize_verified(
            _engine, text, Path(output_path), recognizer=_recognizer, retries=retries, seed=seed
        )
    return _engine.synthesize(text, Path(output_path), seed=seed)


class RenderPool:
    """A fixed set of synthesis workers shared by the job queue's consumers."""

    def __init__(
        self, workers: int, threads_per_worker: int, verify: bool, retries: int, engine: str = "xtts"
    ):
        self.workers = workers
        self._init_args = (threads_per_worker, workers, verify, engine)
        self._retries = retries
        self._executor: ProcessPoolExecutor | None = None
        self._lock = threading.Lock()

    def _pool(self) -> ProcessPoolExecutor:
        with self._lock:
            if self._executor is None:
                self._executor = ProcessPoolExecutor(
                    max_workers=self.workers,
                    mp_context=get_context("spawn"),
                    initializer=_init_worker,
                    initargs=self._init_args,
                )
            return self._executor

    def render(self, text: str, output_path: Path, seed: int | None = None) -> tuple[Path, float]:
        """Render a chunk on the next free worker; blocks until it is written.

        A worker that dies (OOM, segfault) breaks the whole executor, so it is
        discarded and rebuilt on the next call; the chunk in flight still fails
        and is left for the queue's normal failed-chunk handling.
        """
        pool = self._pool()
        try:
            return pool.submit(_render, text, str(output_path), self._retries, seed).result()
        except BrokenProcessPool:
            logger.error("A synthesis worker died; restarting the pool")
            self._discard(pool)
            raise

    def _discard(self, pool: ProcessPoolExecutor) -> None:
        # A second consumer failing on the same broken pool must not discard its replacement.
        with self._lock:
            if self._executor is pool:
                self._executor = None
        pool.shutdown(wait=False, cancel_futures=True)

    def shutdown(self) -> None:
        with self._lock:
            pool, self._executor = self._executor, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
