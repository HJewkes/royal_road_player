"""chatterbox-vllm batch worker: one loaded model, a chapter per request line.

Run as `python -I chatterbox_vllm_worker.py --max-batch N [--no-watermark]
--idle-timeout S` under the chatterbox-vllm venv (`make setup-chatterbox-vllm`),
with cwd at the clone: the port resolves `./t3-model` from cwd. CFG is
process-global in the port, so it arrives as env CHATTERBOX_CFG_SCALE, never as a
kwarg; a worker serves one CFG for its whole life. It imports nothing from `src`;
VllmBatchRenderer (batch.py) drives it over a pipe.

Protocol: once loaded it writes {"ready": true}. Each request line holds the
reference, the sampling kwargs, `diffusion_steps`, the post-processing numbers
and `items` [{index, text, out}]. The port generates `max_batch` items' speech
tokens at a time with T3; its one-take-at-a-time S3Gen is swapped for
BatchedS3Gen (s3gen_batch.py), which decodes them in padded sub-batches. Each
take is sped up by `tempo` (ffmpeg atempo), watermarked with Perth as stock
chatterbox-tts does, then loudness-normalised and padded by finish_take, and
written PCM_16. One reply line per item goes out as each batch finishes:
{index, ok, audio_s, raw_lufs} or {index, ok: false, error}; then {"done": true}
ends the chapter. A batch that fails to generate ends the chapter with
{"done": true, "error"} and the worker exits, since a failed CUDA context is not
worth reusing. With no request for `idle-timeout` seconds, or at end of input,
the worker shuts the model down and exits, freeing the GPU. Replies go to a copy
of the original stdout and fd 1 is pointed at stderr, because vLLM and the port
print to stdout.
"""

import argparse
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np


def _protocol_channel():
    sys.stdout.flush()
    channel = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return channel


# vLLM logs to stdout from its import on, so the reply channel is split off first.
# Its spawned engine process re-imports this module as __mp_main__ with fd 1 already on stderr.
CHANNEL = _protocol_channel() if __name__ == "__main__" else None

# vLLM's engine runs in a spawned process that re-imports this module; the port's
# model and tokenizer register with vLLM on import, so this must stay top level.
from chatterbox_vllm.tts import ChatterboxTTS  # noqa: E402

MAX_MODEL_LEN = 1500
# Padded speech tokens (reference prompt included) per S3Gen sub-batch; bounds its VRAM.
S3GEN_MAX_PADDED_TOKENS = 4000
# Autocast dtype for the S3Gen flow; None keeps the port's fp32.
S3GEN_FLOW_DTYPE = "float16"
SAMPLING_KWARGS = ("exaggeration", "temperature", "min_p", "top_p", "repetition_penalty")


def _load_sibling(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_watermarker(enabled: bool):
    """Perth's implicit watermarker, as stock chatterbox-tts applies; a missing Perth fails the run."""
    if not enabled:
        print("WARNING: Perth watermark disabled for this batch", file=sys.stderr)
        return None
    import perth

    return perth.PerthImplicitWatermarker()


def change_tempo(wav: np.ndarray, sample_rate: int, factor: float) -> np.ndarray:
    """Speed the take up by `factor` without changing pitch (ffmpeg atempo)."""
    if factor == 1.0:
        return wav
    command = [
        "ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
        "-filter:a", f"atempo={factor}", "-f", "f32le", "pipe:1",
    ]
    done = subprocess.run(command, input=np.asarray(wav, dtype=np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(done.stdout, dtype=np.float32)


def write_pcm16(out: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Write mono PCM_16 atomically: a reader never sees a half-written take."""
    partial = out.with_name(out.stem + ".partial.wav")
    with wave.open(str(partial), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((np.clip(audio, -1.0, 1.0) * 32767).round().astype("<i2").tobytes())
    os.replace(partial, out)


class SpeechTokenCollector:
    """Stands in for the port's S3Gen inside generate_with_conds: keeps T3's tokens, decodes nothing."""

    def __init__(self):
        self.tokens = []

    def inference(self, speech_tokens, **_kwargs):
        self.tokens.append(speech_tokens)
        return speech_tokens, None


class BatchWorker:
    def __init__(self, max_batch: int, watermark: bool, results):
        self.max_batch, self.results = max_batch, results
        self.audio = _load_sibling("chatterbox_audio")
        self.watermarker = _load_watermarker(watermark)
        self.model = ChatterboxTTS.from_pretrained(
            max_batch_size=max_batch, max_model_len=MAX_MODEL_LEN, max_num_seqs=max_batch
        )
        self.s3gen = _load_sibling("s3gen_batch").BatchedS3Gen(
            self.model.s3gen, S3GEN_MAX_PADDED_TOKENS, S3GEN_FLOW_DTYPE
        )

    def render(self, request: dict) -> None:
        """Render one chapter's items, max_batch at a time, replying per item."""
        self.request = request
        self.kwargs = {key: float(request["sampling"][key]) for key in SAMPLING_KWARGS}
        self.diffusion_steps = int(request["diffusion_steps"])
        items = request["items"]
        for start in range(0, len(items), self.max_batch):
            self._render_batch(items[start:start + self.max_batch])

    def _render_batch(self, items: list[dict]) -> None:
        began = time.perf_counter()
        wavs = self._generate([item["text"] for item in items])
        if len(wavs) != len(items):
            raise RuntimeError(f"port returned {len(wavs)} takes for {len(items)} texts")
        for item, wav in zip(items, wavs):
            self.emit({"index": item["index"], **self._finish(item, wav)})
        print(f"batch of {len(items)} in {time.perf_counter() - began:.1f}s", file=sys.stderr, flush=True)

    def _generate(self, texts: list[str]) -> list:
        ref, cond_emb = self.model.get_audio_conditionals(self.request["reference"])
        collector, port_s3gen = SpeechTokenCollector(), self.model.s3gen
        self.model.s3gen = collector
        try:
            self.model.generate_with_conds(
                texts, s3gen_ref=ref, cond_emb=cond_emb, diffusion_steps=self.diffusion_steps, **self.kwargs
            )
        finally:
            self.model.s3gen = port_s3gen
        t3_done = time.perf_counter()
        wavs = self.s3gen.wavs(collector.tokens, ref, self.diffusion_steps)
        print(f"S3Gen for {len(texts)} takes in {time.perf_counter() - t3_done:.1f}s", file=sys.stderr, flush=True)
        return wavs

    def _finish(self, item: dict, wav) -> dict:
        try:
            return {"ok": True, **self._post_process(Path(item["out"]), wav)}
        except Exception as exc:  # one bad take must not lose the rest of the batch
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _post_process(self, out: Path, wav) -> dict:
        rate, req = self.model.sr, self.request
        audio = change_tempo(np.asarray(wav, dtype=np.float32).reshape(-1), rate, float(req["tempo"]))
        if self.watermarker is not None:
            audio = self.watermarker.apply_watermark(audio, sample_rate=rate)
        audio, raw_lufs = self.audio.finish_take(audio, rate, float(req["target_lufs"]), float(req["trailing_pad_s"]))
        write_pcm16(out, audio, rate)
        return {"audio_s": round(len(audio) / rate, 3), "raw_lufs": raw_lufs}

    def emit(self, line: dict) -> None:
        self.results.write(json.dumps(line) + "\n")
        self.results.flush()


def _pump_lines(stream, lines: queue.Queue) -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


def serve(worker: BatchWorker, lines: queue.Queue, idle_timeout_s: float) -> None:
    """Render a chapter per request line until input ends or none comes for idle_timeout_s."""
    worker.emit({"ready": True})
    while True:
        try:
            line = lines.get(timeout=idle_timeout_s)
        except queue.Empty:
            print(f"idle for {idle_timeout_s:.0f}s; exiting to free the GPU", file=sys.stderr, flush=True)
            return
        if line is None:
            return
        if not line.strip():
            continue
        try:
            worker.render(json.loads(line))
        except Exception as exc:
            worker.emit({"done": True, "error": f"{type(exc).__name__}: {exc}"})
            raise
        worker.emit({"done": True})


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-batch", type=int, required=True)
    parser.add_argument("--no-watermark", action="store_true")
    parser.add_argument("--idle-timeout", type=float, required=True, help="seconds without a request before exiting")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)
    worker = BatchWorker(args.max_batch, not args.no_watermark, CHANNEL)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_pump_lines, args=(sys.stdin, lines), daemon=True).start()
    try:
        serve(worker, lines, args.idle_timeout)
    finally:
        worker.model.shutdown()


if __name__ == "__main__":
    main()
