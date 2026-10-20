"""Chatterbox TTS engine: a client for the render worker in its own venv.

Chatterbox's stack (transformers 5, numpy<2) cannot share the server's venv, so
each engine owns one `chatterbox_worker.py` subprocess under
`settings.chatterbox_python` and keeps the model loaded there between chunks.
"""

import json
import logging
import queue
import subprocess
import threading
import time
from pathlib import Path

from src.config import get_settings
from src.tts.profiles import P4, ChatterboxProfile

logger = logging.getLogger(__name__)

WORKER = Path(__file__).with_name("chatterbox_worker.py")


class ChatterboxUnavailable(RuntimeError):
    """No usable Chatterbox interpreter or reference on this host."""


class ChatterboxWorkerError(RuntimeError):
    """The worker failed a request, broke the protocol or died."""


class _WorkerExited(ChatterboxWorkerError):
    pass


class ChatterboxEngine:
    """`synthesize(text, path, seed=None, **overrides) -> (path, elapsed)`, like XTTSEngine."""

    def __init__(
        self,
        python: str | None = None,
        reference: str | None = None,
        profile: ChatterboxProfile = P4,
        device: str = "cuda",
        load_timeout_s: float = 600.0,
        request_timeout_s: float = 300.0,
    ):
        settings = get_settings()
        self.python = settings.chatterbox_python if python is None else python
        self.reference = settings.chatterbox_reference_path if reference is None else reference
        _check_runnable(self.python, self.reference)
        self.profile = profile
        self.device = device
        self.load_timeout_s = load_timeout_s
        self.request_timeout_s = request_timeout_s
        self._process: subprocess.Popen | None = None
        self._replies: queue.Queue = queue.Queue()

    def synthesize(
        self, text: str, output_path: Path, seed: int | None = None, **overrides: float
    ) -> tuple[Path, float]:
        """Render one chunk to a 24 kHz PCM_16 wav; elapsed is generation wall time."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        request = {"text": text, "out": str(output_path.resolve()), "seed": seed, **self._params(overrides)}
        self._ensure_worker()  # like XTTS, model load is not generation time
        start = time.perf_counter()
        reply = self._request(request)
        if not reply.get("ok"):
            raise ChatterboxWorkerError(f"Chatterbox failed {output_path.name}: {reply.get('error')}")
        return output_path, time.perf_counter() - start

    def load_model(self) -> None:
        """Start the worker and load the model now rather than on the first chunk."""
        self._ensure_worker()

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _params(self, overrides: dict[str, float]) -> dict[str, float]:
        params = self.profile.generate_kwargs()
        unknown = set(overrides) - set(params)
        if unknown:
            raise TypeError(f"unknown Chatterbox params: {sorted(unknown)}")
        params.update(overrides)
        params["target_lufs"] = self.profile.target_lufs
        params["trailing_pad_s"] = self.profile.trailing_pad_s
        return params

    def _request(self, request: dict) -> dict:
        try:
            return self._exchange(request)
        except _WorkerExited:
            logger.warning("Chatterbox worker exited; respawning it for this chunk")
            self.close()
            return self._exchange(request)

    def _exchange(self, request: dict) -> dict:
        self._ensure_worker()
        try:
            self._process.stdin.write(json.dumps(request) + "\n")
            self._process.stdin.flush()
        except OSError as exc:  # BrokenPipeError: it died since the last chunk
            raise _WorkerExited("worker pipe closed") from exc
        return self._read_reply(self.request_timeout_s)

    def _ensure_worker(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self.close()
        self._spawn()
        ready = self._read_reply(self.load_timeout_s)
        if not ready.get("ready"):
            raise ChatterboxWorkerError(f"Chatterbox worker did not start: {ready}")
        logger.info(f"Chatterbox worker ready (pid {self._process.pid}, {ready.get('sample_rate')} Hz)")

    def _spawn(self) -> None:
        command = [
            self.python, "-I", str(WORKER), "--reference", str(self.reference),
            "--device", self.device, "--exaggeration", str(self.profile.exaggeration),
        ]
        self._process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1
        )
        self._replies = queue.Queue()
        threading.Thread(target=_pump_lines, args=(self._process.stdout, self._replies), daemon=True).start()

    def _read_reply(self, timeout_s: float) -> dict:
        try:
            line = self._replies.get(timeout=timeout_s)
        except queue.Empty:
            self._process.kill()
            raise ChatterboxWorkerError(f"Chatterbox worker gave no reply in {timeout_s:.0f}s") from None
        if line is None:
            raise _WorkerExited("worker exited")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChatterboxWorkerError(f"Chatterbox worker broke the protocol: {line[:200]!r}") from exc


def _pump_lines(stream, replies: queue.Queue) -> None:
    for line in stream:
        replies.put(line)
    replies.put(None)


def _check_runnable(python: str, reference: str) -> None:
    if not python:
        raise ChatterboxUnavailable(
            "Chatterbox needs its own interpreter: set AUDIOBOOK_CHATTERBOX_PYTHON to the "
            "venv-chatterbox python (make setup-chatterbox)"
        )
    if not Path(python).is_file():
        raise ChatterboxUnavailable(f"AUDIOBOOK_CHATTERBOX_PYTHON does not exist: {python}")
    if not Path(reference).is_file():
        raise ChatterboxUnavailable(f"Chatterbox voice reference not found: {reference}")
